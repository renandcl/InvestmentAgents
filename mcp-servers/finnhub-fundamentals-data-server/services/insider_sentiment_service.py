import os
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta

import finnhub

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")


class FinnhubInsiderSentimentService:
    def __init__(self):
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

        file_path = f"data/insider_sentiment_data/finnhub_insider_sentiment_{ticker}_{before}_{curr_date}.json"

        if os.path.exists(file_path):
            json_data = json.load(open(file_path, "r"))
        else:
            json_data = self.client.stock_insider_sentiment(
                ticker,
                before,
                curr_date,
            )

            os.makedirs("data/insider_sentiment_data", exist_ok=True)
            json.dump(json_data, open(file_path, "w"))

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
