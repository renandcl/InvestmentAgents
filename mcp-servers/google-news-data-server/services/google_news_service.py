import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from tenacity import retry, retry_if_result, stop_after_attempt, wait_exponential


def is_rate_limited(response):
    return response.status_code == 429


@retry(
    retry=(retry_if_result(is_rate_limited)),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
)
def make_request(url, headers):
    time.sleep(random.uniform(2, 6))
    response = requests.get(url, headers=headers)
    return response


class GoogleNewsService:
    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/101.0.4951.54 Safari/537.36"
            )
        }

    def _scrape(self, query: str, start_date: str, end_date: str) -> List[Dict]:
        results: List[Dict] = []
        page = 0
        while True:
            offset = page * 10
            url = (
                f"https://www.google.com/search?q={query}"
                f"&tbs=cdr:1,cd_min:{start_date},cd_max:{end_date}"
                f"&tbm=nws&start={offset}"
            )
            response = make_request(url, self.headers)
            soup = BeautifulSoup(response.content, "html.parser")
            results_on_page = soup.select("div.SoaBEf")
            if not results_on_page:
                break
            for el in results_on_page:
                try:
                    link = el.find("a")["href"]
                    title = el.select_one("div.MBeuO").get_text()
                    snippet = el.select_one(".GI74Re").get_text()
                    date = el.select_one(".LfVVr").get_text()
                    source = el.select_one(".NUnG9d span").get_text()
                    results.append(
                        {
                            "link": link,
                            "title": title,
                            "snippet": snippet,
                            "date": date,
                            "source": source,
                        }
                    )
                except Exception:
                    continue
            next_link = soup.find("a", id="pnnext")
            if not next_link:
                break
            page += 1
        return results

    def get_news(self, query: str, curr_date: str, look_back_days: int) -> str:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        before = curr_dt - relativedelta(days=look_back_days)
        before_str = before.strftime("%Y-%m-%d")

        os.makedirs("data/news_data", exist_ok=True)
        file_path = f"data/news_data/google_news_{query}_{before_str}_{curr_date}.json"

        if os.path.exists(file_path):
            json_data = json.load(open(file_path, "r"))
        else:
            # Google date parameters want mm/dd/yyyy
            start_scrape = before.strftime("%m/%d/%Y")
            end_scrape = curr_dt.strftime("%m/%d/%Y")
            query_enc = query.replace(" ", "+")
            articles = self._scrape(query_enc, start_scrape, end_scrape)
            json_data = {"data": articles}
            json.dump(json_data, open(file_path, "w"))

        if len(json_data["data"]) == 0:
            return "No news data available for this query."

        combined = ""
        count = 0
        for entry in json_data["data"]:
            combined += (
                f"### {entry['title']}\nSource: {entry['source']} | Date: {entry['date']}\n"
                f"{entry['snippet']}\nURL: {entry['link']}\n\n"
            )
            count += 1
            if count >= 20:
                break

        return (
            f"## {query} Google News, from {before_str} to {curr_date}:\n\n" + combined
        )


if __name__ == "__main__":
    service = GoogleNewsService()
    print(service.get_news("AAPL", "2025-08-25", 30))
