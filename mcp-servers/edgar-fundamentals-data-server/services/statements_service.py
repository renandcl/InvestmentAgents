from __future__ import annotations

from typing import TYPE_CHECKING

from runtime.providers.cache import service_cache

from .edgar_service import download, latest_statement

if TYPE_CHECKING:
    from runtime.providers.cache import RunCache


class EdgarStatementsService:
    def __init__(self, *, cache: RunCache | None = None) -> None:
        self.cache = service_cache("edgar-fundamentals-data-server", cache)

    def get_statement(self, source: str, ticker: str, freq: str, curr_date: str) -> str:
        key = self.cache.key("companyfacts", {"ticker": ticker})
        cached = self.cache.read_json(key)
        if cached is None:
            cached = {"data": [download(ticker)]}
            self.cache.write_json(key, cached)
        return latest_statement(cached["data"][0], source, ticker, freq, curr_date)
