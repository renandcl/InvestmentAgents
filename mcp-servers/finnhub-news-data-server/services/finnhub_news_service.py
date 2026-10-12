import os
from datetime import datetime, timezone

import finnhub
from dateutil.relativedelta import relativedelta

from runtime.cache import service_cache

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")


class FinnhubNewsService:
    def __init__(self, *, cache=None):
        self.cache = service_cache("finnhub-news-data-server", cache)
        self.client = finnhub.Client(api_key=FINNHUB_API_KEY)

    def get_news(
        self,
        ticker: str,
        curr_date: str,
        look_back_days: int,
    ):
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
