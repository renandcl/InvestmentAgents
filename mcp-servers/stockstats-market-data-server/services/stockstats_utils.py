from io import StringIO
from typing import Annotated

import pandas as pd
import yfinance as yf
from stockstats import wrap

from runtime.cache import CacheCorruption, service_cache


class StockstatsUtils:
    @staticmethod
    def price_data(cache, symbol, start_date, end_date):
        cache = service_cache("stockstats-market-data-server", cache)
        key = cache.key(
            "prices",
            {"symbol": symbol, "start": start_date, "end": end_date, "adjust": True},
            extension="csv",
        )
        text = cache.read_text(key)
        if text is None:
            data = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                multi_level_index=False,
                progress=False,
                auto_adjust=True,
            ).reset_index()
            text = data.to_csv(index=False)
            cache.write_text(key, text)
        try:
            data = pd.read_csv(StringIO(text))
            if "Date" not in data.columns:
                raise ValueError
            data["Date"] = pd.to_datetime(data["Date"])
            return data
        except (ValueError, pd.errors.ParserError):
            raise CacheCorruption("Invalid cached price data") from None

    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
        end_date: Annotated[
            str, "end date for retrieving stock price data, YYYY-mm-dd"
        ],
        *,
        cache,
    ):
        df = None
        data = None
        # 15 years ago from today
        end_date = pd.to_datetime(end_date)
        start_date = end_date - pd.DateOffset(years=15)
        start_date = start_date.strftime("%Y-%m-%d")
        end_date = end_date.strftime("%Y-%m-%d")

        data = StockstatsUtils.price_data(cache, symbol, start_date, end_date)
        df = wrap(data)
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
