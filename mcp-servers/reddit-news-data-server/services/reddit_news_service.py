from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import praw
from praw.models import Submission

from runtime.providers.cache import service_cache
from runtime.providers.capture import read_slice, slice_finished, write_slice
from runtime.providers.timecut import NEW_YORK, Record, parse_instant

if TYPE_CHECKING:
    from runtime.providers.cache import RunCache

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
SENTIMENT_SEARCH_LIMIT = 250
SENTIMENT_CAPPED_POSTS = 200
ACTIVE_SUBREDDITS = ("stocks", "investing", "ValueInvesting", "Daytrading", "options")
REACHED_SUBREDDITS = 3
SOURCE = "reddit_posts"
LOOKBACK_DAYS = 7
COMPANY_NAMES = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "NVDA": "Nvidia",
}
POST_FIELDS = ("id", "title", "selftext", "created_utc", "subreddit", "reddit_url")


def _queries(ticker: str) -> dict[str, str]:
    return {"symbol": ticker, "cashtag": f"${ticker}", "name": COMPANY_NAMES[ticker]}


def fetch(request: dict[str, Any], output: Path) -> None:
    """Store newest-first searches without engagement counts, which postdate D."""
    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=REDDIT_USER_AGENT,
    )
    reddit.read_only = True
    for name in SENTIMENT_SUBREDDITS:
        for variant, query in _queries(request["ticker"]).items():
            slice_name = f"{name}-{variant}"
            if slice_finished(output, slice_name):
                continue
            posts = [
                {
                    "id": str(post.id),
                    "title": post.title,
                    "selftext": post.selftext,
                    "created_utc": post.created_utc,
                    "subreddit": post.subreddit.display_name,
                    "reddit_url": "https://www.reddit.com" + post.permalink,
                }
                for post in reddit.subreddit(name).search(
                    query, sort="new", time_filter="all", limit=SENTIMENT_SEARCH_LIMIT
                )
            ]
            write_slice(output, slice_name, posts)


def _searches(request: dict[str, Any], raw: Path) -> dict[str, list[list[dict]]]:
    return {
        name: [
            read_slice(raw, f"{name}-{variant}")
            for variant in _queries(request["ticker"])
        ]
        for name in SENTIMENT_SUBREDDITS
    }


def normalize(request: dict[str, Any], raw: Path) -> list[Record]:
    records = []
    for searches in _searches(request, raw).values():
        for posts in searches:
            for post in posts:
                if post.get("created_utc") is None:
                    continue
                public_at = datetime.datetime.fromtimestamp(
                    post["created_utc"], tz=datetime.timezone.utc
                )
                payload = {field: post.get(field) for field in POST_FIELDS}
                records.append(Record(payload["id"], public_at, SOURCE, payload))
    return records


def search_reached(posts: list[dict[str, Any]], required: float) -> bool:
    """A capped search reaches the start only when it holds an older post."""
    if len(posts) < SENTIMENT_CAPPED_POSTS:
        return True
    return any((post.get("created_utc") or required) < required for post in posts)


def coverage(request: dict[str, Any], raw: Path) -> dict[str, dict[str, Any]]:
    """Three of the five active subreddits must reach the 7-day lookback."""
    searches = _searches(request, raw)
    records = normalize(request, raw)
    dropped = sum(
        post.get("created_utc") is None
        for found in searches.values()
        for posts in found
        for post in posts
    )
    entries = {}
    for item in request["candidates"]:
        cutoff = parse_instant(item["cutoff"])
        required = cutoff - datetime.timedelta(days=LOOKBACK_DAYS)
        subreddits = {
            name: {
                "reached": (
                    reached := all(
                        search_reached(posts, required.timestamp()) for posts in found
                    )
                ),
                "truncated": not reached,
            }
            for name, found in searches.items()
        }
        admitted = {r.id for r in records if required <= r.public_at <= cutoff}
        entries[item["date"]] = {
            SOURCE: {
                "reachable": True,
                "records": len(admitted),
                "truncated": any(s["truncated"] for s in subreddits.values()),
                "required_start": required.astimezone(NEW_YORK).date().isoformat(),
                "coverage_rule_met": sum(
                    subreddits[name]["reached"] for name in ACTIVE_SUBREDDITS
                )
                >= REACHED_SUBREDDITS,
                "subreddits": subreddits,
                "dropped_rows": dropped,
            }
        }
    return entries


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
                "capped": scanned >= SENTIMENT_CAPPED_POSTS and not reached_start,
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
