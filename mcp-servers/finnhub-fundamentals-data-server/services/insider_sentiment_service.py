import os
from datetime import datetime

import finnhub
from dateutil.relativedelta import relativedelta

from runtime.cache import service_cache

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")


class FinnhubInsiderSentimentService:
    def __init__(self, *, cache=None):
        self.cache = service_cache("finnhub-fundamentals-data-server", cache)
        self.client = finnhub.Client(api_key=FINNHUB_API_KEY)

    def get_insider_sentiment(
        self,
        ticker: str,
        curr_date: str,
        look_back_days: int,
    ):
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
