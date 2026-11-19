from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import finnhub
from dateutil.relativedelta import relativedelta

from runtime.providers.cache import service_cache
from runtime.providers.capture import fetch_windows, read_windows, window_coverage
from runtime.providers.timecut import (
    NEW_YORK,
    Record,
    last_admitted_date,
    parse_instant,
)

if TYPE_CHECKING:
    from runtime.providers.cache import RunCache

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
SOURCE = "finnhub_news"
LOOKBACK_DAYS = 7
NEWS_PAGE_MAX: int | None = None


def fetch(request: dict[str, Any], output: Path) -> None:
    client = finnhub.Client(api_key=os.environ["FINNHUB_API_KEY"])
    cutoffs = [parse_instant(item["cutoff"]) for item in request["candidates"]]
    first = (min(cutoffs).astimezone(NEW_YORK) - timedelta(days=LOOKBACK_DAYS)).date()

    def window(start: date, end: date) -> list[dict[str, Any]]:
        articles = client.company_news(
            request["ticker"], _from=start.isoformat(), to=end.isoformat()
        )
        return articles or []

    fetch_windows(
        output,
        SOURCE,
        first,
        last_admitted_date(max(cutoffs)),
        window,
        NEWS_PAGE_MAX,
    )


def _records(raw: Path) -> tuple[list[Record], int]:
    records = []
    dropped = 0
    for window in read_windows(raw, SOURCE):
        for article in window["rows"]:
            stamp = article.get("datetime")
            if not isinstance(stamp, int) or stamp <= 0:
                dropped += 1
                continue
            public_at = datetime.fromtimestamp(stamp, tz=timezone.utc)
            identifier = str(article.get("id") or article.get("url"))
            records.append(Record(identifier, public_at, SOURCE, article))
    return records, dropped


def normalize(request: dict[str, Any], raw: Path) -> list[Record]:
    return _records(raw)[0]


def coverage(request: dict[str, Any], raw: Path) -> dict[str, dict[str, Any]]:
    records, dropped = _records(raw)
    windows = read_windows(raw, SOURCE)
    return {
        item["date"]: {
            SOURCE: window_coverage(
                records, windows, item, LOOKBACK_DAYS, NEWS_PAGE_MAX, dropped
            )
        }
        for item in request["candidates"]
    }


class FinnhubNewsService:
    def __init__(self, *, cache: RunCache | None = None) -> None:
        self.cache = service_cache("finnhub-news-data-server", cache)
        self.client = finnhub.Client(api_key=FINNHUB_API_KEY)

    def get_news(
        self,
        ticker: str,
        curr_date: str,
        look_back_days: int,
    ) -> str:
        """
        Retrieve news about a company within a time frame

        Args
            ticker (str): ticker for the company you are interested in
            curr_date (str): Current date in yyyy-mm-dd format
            look_back_days (int): how many days to look back
        Returns
            str: dataframe containing the news of the company in the time frame

        """

        start_date = datetime.strptime(curr_date, "%Y-%m-%d")
        before = start_date - relativedelta(days=look_back_days)
        before = before.strftime("%Y-%m-%d")

        key = self.cache.key(
            "news", {"ticker": ticker, "before": before, "current_date": curr_date}
        )
        json_data = self.cache.read_json(key)
        if json_data is None:
            json_data = {"data": self.client.company_news(ticker, before, curr_date)}

            self.cache.write_json(key, json_data)

        if len(json_data["data"]) == 0:
            return "No news data available for this company."

        combined_result = ""
        for entry in json_data["data"]:
            headline = entry.get("headline", "")
            summary = entry.get("summary", "")
            source = entry.get("source", "")
            url = entry.get("url", "")
            dt = entry.get("datetime", None)
            date_str = (
                datetime.fromtimestamp(dt, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                if dt
                else ""
            )
            combined_result += f"### {headline} ({date_str})\nSource: {source}\n{summary}\nURL: {url}\n\n"

        return f"## {ticker} News, from {before} to {curr_date}:\n" + str(
            combined_result
        )


if __name__ == "__main__":
    finnhub_service = FinnhubNewsService()
    data = finnhub_service.get_news("AAPL", "2025-08-05", 30)
    print(data)
