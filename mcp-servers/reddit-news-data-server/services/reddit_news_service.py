import datetime
import os

import praw
from praw.models import Submission

from runtime.cache import service_cache

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")


class RedditNewsService:
    def __init__(self, *, cache=None):
        self.cache = service_cache("reddit-news-data-server", cache)
        self.reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent="fundamentals_news_agent",
        )
        self.reddit.read_only = True

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

        start_date = datetime.datetime.strptime(curr_date, "%Y-%m-%d")
        before = start_date - datetime.timedelta(days=look_back_days)

        key = self.cache.key(
            "news",
            {
                "ticker": ticker,
                "current_date": curr_date,
                "look_back_days": look_back_days,
            },
        )
        json_data = self.cache.read_json(key)
        if json_data is not None:
            # subreddit : List[Submission] = json_data["data"]
            subreddit = []
            for item in json_data["data"]:
                item["id"] = None
                subreddit.append(Submission(self.reddit, _data=item))
        else:
            subreddit = list(
                self.reddit.subreddit("all").search(
                    f"{ticker} financial performance analysis"
                )
            )

            json_data = {"data": []}

            for submission in subreddit:
                json_data["data"].append(
                    {
                        "title": submission.title,
                        "selftext": submission.selftext,
                        "created_utc": submission.created_utc,
                    }
                )
            self.cache.write_json(key, json_data)

        combined_result = ""
        count_submissions = 0
        for submission in subreddit:
            if submission.created_utc < before.timestamp():
                continue
            if submission.created_utc > start_date.timestamp():
                continue
            title = submission.title
            selftext = submission.selftext
            combined_result += f"### Title: {title}\n"
            combined_result += (
                f"Date: {datetime.datetime.fromtimestamp(submission.created_utc)}\n"
            )
            combined_result += f"Content: {selftext}\n\n"
            combined_result += "-" * 20 + "\n"
            count_submissions += 1
            if count_submissions >= 10:
                break

        if not combined_result:
            return "No news data available for this company."

        return f"##{ticker} News Reddit, from {before} to {curr_date}:\n\n{combined_result}"


if __name__ == "__main__":
    service = RedditNewsService()
    print(service.get_news("AAPL", "2025-08-20", 30))
