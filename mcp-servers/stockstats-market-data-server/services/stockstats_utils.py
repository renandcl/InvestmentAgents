import os
from typing import Annotated

import pandas as pd
import yfinance as yf
from stockstats import wrap


class StockstatsUtils:
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
    ):
        df = None
        data = None
        # 15 years ago from today
        end_date = pd.to_datetime(end_date)
        start_date = end_date - pd.DateOffset(years=15)
        start_date = start_date.strftime("%Y-%m-%d")
        end_date = end_date.strftime("%Y-%m-%d")

        file_path = (
            f"data/market_data/yfin_stockstats_{symbol}_{curr_date}_{end_date}.csv"
        )

        if os.path.exists(file_path):
            try:
                data = pd.read_csv(file_path)
                df = wrap(data)
            except FileNotFoundError:
                raise Exception("Stockstats fail: Yahoo Finance data not fetched yet!")
        else:
            if os.path.exists(file_path):
                data = pd.read_csv(file_path)
                data["Date"] = pd.to_datetime(data["Date"])
            else:
                data = yf.download(
                    symbol,
                    start=start_date,
                    end=end_date,
                    multi_level_index=False,
                    progress=False,
                    auto_adjust=True,
                )
                data = data.reset_index()
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                data.to_csv(file_path, index=False)

            df = wrap(data)
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
