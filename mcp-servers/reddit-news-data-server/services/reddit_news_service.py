from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING, Any

import praw
from praw.models import Submission

from runtime.cache import service_cache

if TYPE_CHECKING:
    from runtime.cache import RunCache

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
# Reddit's API rules require <platform>:<app ID>:<version> (by /u/<username>).
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", "unknown")
REDDIT_USER_AGENT = (
    f"python:investmentagents.reddit-news:0.1.0 (by /u/{REDDIT_USERNAME})"
)
SENTIMENT_SUBREDDITS = (
    "stocks",
    "investing",
    "finance",
    "ValueInvesting",
    "Daytrading",
    "options",
)
SENTIMENT_SEARCH_LIMIT = 1000


class RedditNewsService:
    def __init__(self, *, cache: RunCache | None = None) -> None:
        self.cache = service_cache("reddit-news-data-server", cache)
        self.reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        self.reddit.read_only = True

    def get_sentiment(
        self, ticker: str, start_date: str, end_date: str, max_posts: int = 30
    ) -> dict[str, Any]:
        """Return a bounded, dated sample of opinions with source provenance."""
        ticker = ticker.strip().upper()
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        )
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        )
        if not ticker or start > end or not 1 <= max_posts <= 100:
            raise ValueError("Invalid sentiment sample parameters")
        cutoff = end + datetime.timedelta(days=1)
        key = self.cache.key(
            "sentiment-v2",
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "max_posts": max_posts,
                "subreddits": SENTIMENT_SUBREDDITS,
                "search_limit": SENTIMENT_SEARCH_LIMIT,
                "sort": "new",
            },
        )
        cached = self.cache.read_json(key)
        if cached is not None:
            return cached
        posts = {}
        coverage = {}
        for name in SENTIMENT_SUBREDDITS:
            scanned = 0
            oldest = None
            reached_start = False
            for post in self.reddit.subreddit(name).search(
                ticker, sort="new", time_filter="all", limit=SENTIMENT_SEARCH_LIMIT
            ):
                scanned += 1
                oldest = (
                    post.created_utc
                    if oldest is None
                    else min(oldest, post.created_utc)
                )
                if post.created_utc < start.timestamp():
                    reached_start = True
                    break
                if not start.timestamp() <= post.created_utc < cutoff.timestamp():
                    continue
                post_id = str(post.id)
                if post_id in posts:
                    continue
                posts[post_id] = {
                    "id": post_id,
                    "title": post.title,
                    "selftext": post.selftext,
                    "created_utc": post.created_utc,
                    "subreddit": post.subreddit.display_name,
                    "reddit_url": "https://www.reddit.com" + post.permalink,
                    "score": post.score,
                    "num_comments": post.num_comments,
                }
            coverage[name] = {
                "scanned": scanned,
                "oldest_returned_utc": oldest,
                "window_reached": oldest is not None and oldest < cutoff.timestamp(),
                "capped": scanned >= SENTIMENT_SEARCH_LIMIT and not reached_start,
            }
        sample = sorted(
            posts.values(), key=lambda post: (-post["created_utc"], post["id"])
        )[:max_posts]
        inaccessible = any(
            item["scanned"] and not item["window_reached"] for item in coverage.values()
        )
        truncated = inaccessible or any(item["capped"] for item in coverage.values())
        result = {
            "status": (
                ("partial" if truncated else "ok")
                if sample
                else ("unavailable" if inaccessible else "no_data")
            ),
            "coverage": coverage,
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "UTC",
            "subreddits": list(SENTIMENT_SUBREDDITS),
            "query": ticker,
            "sort": "new",
            "search_limit_per_subreddit": SENTIMENT_SEARCH_LIMIT,
            "max_posts": max_posts,
            "sample_size": len(sample),
            "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "limitations": "Bounded paginated search, not an historical archive; an unreached window is unavailable. Comments are not fetched. Engagement is observed at retrieval time, not historical. Empty results do not imply neutral sentiment.",
            "data": sample,
        }
        self.cache.write_json(key, result)
        return result

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
