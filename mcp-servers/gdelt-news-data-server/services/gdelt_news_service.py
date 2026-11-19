"""GDELT DOC 2.0 article capture for the study dataset (spec 006)."""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from runtime.providers.capture import slice_finished, write_slice
from runtime.providers.timecut import NEW_YORK, Record, parse_instant

SOURCE = "gdelt_news"
API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
LOOKBACK_DAYS = 7
MAX_RECORDS = 250
PAUSE_SECONDS = 20
TIMEOUT_SECONDS = 60
RETRY_WAITS = (30, 60, 120, 240)
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


def _articles(query: str, cutoff: datetime) -> list[dict[str, Any]] | None:
    """Request the 7 days ending at the cutoff; None after exhausted retries."""
    params = {
        "query": f"{query} sourcelang:english",
        "mode": "artlist",
        "format": "json",
        "maxrecords": MAX_RECORDS,
        "sort": "hybridrel",
        "startdatetime": (cutoff - timedelta(days=LOOKBACK_DAYS)).strftime(
            QUERY_FORMAT
        ),
        "enddatetime": cutoff.strftime(QUERY_FORMAT),
    }
    request = Request(f"{API_URL}?{urlencode(params)}")
    for wait in (*RETRY_WAITS, None):
        time.sleep(PAUSE_SECONDS)
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read() or b"{}").get("articles") or []
        except (URLError, TimeoutError, ValueError):
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
            articles = _articles(query, cutoff)
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
