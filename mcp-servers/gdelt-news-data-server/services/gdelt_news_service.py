"""GDELT DOC 2.0 article search for the news tool and study dataset (spec 006)."""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from datetime import time as day_start
from http.client import HTTPException
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from runtime.providers.cache import service_cache
from runtime.providers.capture import slice_finished, write_slice
from runtime.providers.timecut import NEW_YORK, Record, parse_instant

if TYPE_CHECKING:
    from runtime.providers.cache import RunCache

SOURCE = "gdelt_news"
API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
LOOKBACK_DAYS = 7
MAX_RECORDS = 250
PAUSE_SECONDS = 20
TIMEOUT_SECONDS = 60
RETRY_WAITS = (30, 60, 120, 240)
TOOL_PAUSE_SECONDS = 5
TOOL_RETRY_WAITS = (30, 60)
TOOL_MAX_RESULTS = 50
TICKER_QUERIES = {
    "AAPL": '("Apple" OR AAPL)',
    "MSFT": '("Microsoft" OR MSFT)',
    "GOOGL": '("Alphabet" OR "Google" OR GOOGL)',
    "AMZN": '("Amazon" OR AMZN)',
    "META": '("Meta Platforms" OR META)',
    "TSLA": '("Tesla" OR TSLA)',
    "NVDA": '("Nvidia" OR NVDA)',
}
MACRO_QUERY = (
    '("Federal Reserve" OR inflation OR "interest rates" OR recession OR tariffs'
    ' OR "stock market")'
)
SEEN_FORMAT = "%Y%m%dT%H%M%SZ"
QUERY_FORMAT = "%Y%m%d%H%M%S"


def _pools(request: dict[str, Any], raw: Path) -> dict[str, tuple[str, Path]]:
    """Ticker pools live per ticker; the macro pool is shared by every ticker."""
    return {
        "ticker": (TICKER_QUERIES[request["ticker"]], raw),
        "macro": (MACRO_QUERY, raw.parent / "macro"),
    }


def search(
    query: str,
    start: datetime,
    end: datetime,
    pause: int = PAUSE_SECONDS,
    waits: tuple[int, ...] = RETRY_WAITS,
) -> list[dict[str, Any]] | None:
    """Articles GDELT first saw between start and end; None after exhausted retries."""
    params = {
        "query": f"{query} sourcelang:english",
        "mode": "artlist",
        "format": "json",
        "maxrecords": MAX_RECORDS,
        "sort": "hybridrel",
        "startdatetime": start.astimezone(timezone.utc).strftime(QUERY_FORMAT),
        "enddatetime": end.astimezone(timezone.utc).strftime(QUERY_FORMAT),
    }
    request = Request(f"{API_URL}?{urlencode(params)}")
    for wait in (*waits, None):
        time.sleep(pause)
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read() or b"{}").get("articles") or []
        except (OSError, HTTPException, ValueError):
            if wait is None:
                return None
            time.sleep(wait)
    return None


def fetch(request: dict[str, Any], output: Path) -> None:
    """An unreachable window is left unfinished, so a resumed capture retries it."""
    for item in request["candidates"]:
        cutoff = parse_instant(item["cutoff"])
        for pool, (query, folder) in _pools(request, output).items():
            name = f"{pool}-{item['date']}"
            if slice_finished(folder, name):
                continue
            articles = search(query, cutoff - timedelta(days=LOOKBACK_DAYS), cutoff)
            if articles is not None:
                write_slice(folder, name, articles)


def _window(
    request: dict[str, Any], raw: Path, item: dict[str, str]
) -> tuple[list[Record], dict[str, Any]]:
    cutoff = parse_instant(item["cutoff"])
    records: dict[str, Record] = {}
    reachable = True
    truncated = False
    dropped = 0
    for pool, (_, folder) in _pools(request, raw).items():
        path = folder / f"{pool}-{item['date']}.json"
        if not slice_finished(folder, f"{pool}-{item['date']}"):
            reachable = False
            continue
        articles = json.loads(path.read_text(encoding="utf-8"))
        truncated = truncated or len(articles) >= MAX_RECORDS
        for article in articles:
            try:
                seen = datetime.strptime(article.get("seendate", ""), SEEN_FORMAT)
            except ValueError:
                dropped += 1
                continue
            seen = seen.replace(tzinfo=timezone.utc)
            url = article.get("url")
            if not url or seen > cutoff or url in records:
                continue
            payload = {
                "title": article.get("title", ""),
                "domain": article.get("domain", ""),
                "url": url,
                "seendate": article["seendate"],
                "pool": pool,
                "window": item["date"],
            }
            records[url] = Record(f"{item['date']}|{url}", seen, SOURCE, payload)
    days = Counter(
        record.public_at.astimezone(NEW_YORK).date().isoformat()
        for record in records.values()
    )
    entry = {
        "reachable": reachable,
        "records": len(records),
        "truncated": truncated,
        "earliest_reached": min(days, default=None),
        "latest_reached": max(days, default=None),
        "required_start": (cutoff.astimezone(NEW_YORK) - timedelta(days=LOOKBACK_DAYS))
        .date()
        .isoformat(),
        "coverage_rule_met": reachable,
        "per_day_articles": dict(sorted(days.items())),
        "dropped_rows": dropped,
    }
    return list(records.values()), entry


def normalize(request: dict[str, Any], raw: Path) -> list[Record]:
    return [
        record
        for item in request["candidates"]
        for record in _window(request, raw, item)[0]
    ]


def coverage(request: dict[str, Any], raw: Path) -> dict[str, dict[str, Any]]:
    """A truncated window still meets the rule; its daily counts are reported."""
    return {
        item["date"]: {SOURCE: _window(request, raw, item)[1]}
        for item in request["candidates"]
    }


class GdeltNewsService:
    def __init__(self, *, cache: RunCache | None = None) -> None:
        self.cache = service_cache("gdelt-news-data-server", cache)

    def get_news(self, query: str, start_date: str, end_date: str) -> str:
        """Articles first seen from start_date through end_date, inclusive New York dates."""
        key = self.cache.key(
            "news", {"query": query, "start_date": start_date, "end_date": end_date}
        )
        cached = self.cache.read_json(key)
        if cached is None:
            start = datetime.combine(
                date.fromisoformat(start_date), day_start(), NEW_YORK
            )
            end = datetime.combine(
                date.fromisoformat(end_date) + timedelta(days=1), day_start(), NEW_YORK
            )
            articles = search(query, start, end, TOOL_PAUSE_SECONDS, TOOL_RETRY_WAITS)
            if articles is None:
                return "Error: GDELT did not respond; try again later."
            cached = {"data": articles}
            self.cache.write_json(key, cached)
        return format_news(query, start_date, end_date, cached["data"])


def format_news(
    query: str, start_date: str, end_date: str, articles: list[dict[str, Any]]
) -> str:
    """Newest first, one entry per URL, at most 50."""
    unique = {article["url"]: article for article in articles if article.get("url")}
    newest = sorted(
        unique.values(), key=lambda article: article.get("seendate", ""), reverse=True
    )[:TOOL_MAX_RESULTS]
    if not newest:
        return "No news data available for this query."
    entries = "".join(
        f"### {article.get('title', '')}\n"
        f"Source: {article.get('domain', '')} | Date: {article.get('seendate', '')}\n"
        f"URL: {article['url']}\n\n"
        for article in newest
    )
    return f"## {query} GDELT News, from {start_date} to {end_date}:\n\n" + entries
