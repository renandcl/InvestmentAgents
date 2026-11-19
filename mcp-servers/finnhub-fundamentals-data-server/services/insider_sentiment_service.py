from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import finnhub
from dateutil.relativedelta import relativedelta

from runtime.providers.cache import service_cache
from runtime.providers.capture import read_slice, slice_finished, write_slice
from runtime.providers.timecut import Record, parse_instant, public_at_from_date

if TYPE_CHECKING:
    from runtime.providers.cache import RunCache

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
SOURCE = "insider_sentiment"
HISTORY_DAYS = 124


def fetch(request: dict[str, Any], output: Path) -> None:
    """One request from four months before the first candidate to the last."""
    if slice_finished(output, SOURCE):
        return
    client = finnhub.Client(api_key=os.environ["FINNHUB_API_KEY"])
    days = [date.fromisoformat(item["date"]) for item in request["candidates"]]
    start = (min(days) - timedelta(days=HISTORY_DAYS)).isoformat()
    response = client.stock_insider_sentiment(
        request["ticker"], start, max(days).isoformat()
    )
    write_slice(output, SOURCE, response.get("data") or [])


def third_weekday(year: int, month: int) -> date:
    day = date(year, month, 1)
    weekdays = 0
    while True:
        weekdays += day.weekday() < 5
        if weekdays == 3:
            return day
        day += timedelta(days=1)


def _records(raw: Path) -> tuple[list[Record], int]:
    records = []
    dropped = 0
    for row in read_slice(raw, SOURCE):
        year, month = row.get("year"), row.get("month")
        if not year or not month:
            dropped += 1
            continue
        following = date(year + month // 12, month % 12 + 1, 1)
        public_at = public_at_from_date(third_weekday(following.year, following.month))
        records.append(Record(f"{year:04d}-{month:02d}", public_at, SOURCE, row))
    return records, dropped


def normalize(request: dict[str, Any], raw: Path) -> list[Record]:
    return _records(raw)[0]


def coverage(request: dict[str, Any], raw: Path) -> dict[str, dict[str, Any]]:
    """A reachable response meets the rule; an empty month is not a gap."""
    records, dropped = _records(raw)
    entries = {}
    for item in request["candidates"]:
        cutoff = parse_instant(item["cutoff"])
        admitted = sorted(r.id for r in records if r.public_at <= cutoff)
        entries[item["date"]] = {
            "reachable": True,
            "records": len(admitted),
            "truncated": False,
            "earliest_reached": admitted[0] if admitted else None,
            "latest_reached": admitted[-1] if admitted else None,
            "required_start": None,
            "coverage_rule_met": True,
            "dropped_rows": dropped,
        }
    return entries


class FinnhubInsiderSentimentService:
    def __init__(self, *, cache: RunCache | None = None) -> None:
        self.cache = service_cache("finnhub-fundamentals-data-server", cache)
        self.client = finnhub.Client(api_key=FINNHUB_API_KEY)

    def get_insider_sentiment(
        self,
        ticker: str,
        curr_date: str,
        look_back_days: int,
    ) -> str:
        """
        Retrieve insider sentiment data about a company within a time frame

        Args
            ticker (str): ticker for the company you are interested in
            start_date (str): Start date in yyyy-mm-dd format
            end_date (str): End date in yyyy-mm-dd format
        Returns
            str: dataframe containing the insider sentiment of the company in the time frame

        """

        date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
        before = date_obj - relativedelta(days=look_back_days)
        before = before.strftime("%Y-%m-%d")

        key = self.cache.key(
            "insider_sentiment",
            {"ticker": ticker, "before": before, "current_date": curr_date},
        )
        json_data = self.cache.read_json(key)
        if json_data is None:
            json_data = self.client.stock_insider_sentiment(
                ticker,
                before,
                curr_date,
            )

            self.cache.write_json(key, json_data)

        if len(json_data["data"]) == 0:
            return "No insider sentiment data available for this company."

        result_str = ""
        for entry in json_data["data"]:
            result_str += (
                f"### {entry['year']}-{entry['month']}:\n"
                f"Change: {entry['change']}\n"
                f"Monthly Share Purchase Ratio: {entry['mspr']}\n\n"
            )
        return (
            f"## {ticker} Insider Sentiment Data for {before} to {curr_date}:\n"
            + result_str
            + "The change field refers to the net buying/selling from all insiders' transactions. The mspr field refers to monthly share purchase ratio."
        )
