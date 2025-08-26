import os
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict
from ddgs import DDGS

class DuckDuckGoNewsService:
    def __init__(self):
        # DDGS has context manager usage; we will instantiate when querying
        pass

    def get_news(
        self,
        query: str,
        curr_date: str,
        look_back_days: int,
        max_results: int = 20,
        region: str = "us-en",
        safesearch: str = "moderate",
        timelimit: str | None = None,
        backend: str = "auto",
    ) -> str:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        before = curr_dt - relativedelta(days=look_back_days)
        before_str = before.strftime("%Y-%m-%d")

        os.makedirs("data/news_data", exist_ok=True)
        cache_file = (
            "data/news_data/duckduckgo_news_"
            f"{query}_{before_str}_{curr_date}_{max_results}_{region}_{safesearch}_{timelimit or 'auto'}_{backend}.json"
        )

        if os.path.exists(cache_file):
            json_data = json.load(open(cache_file, "r"))
        else:
            # ddgs.news does not support direct date filtering for historical ranges precisely; we fetch and then filter
            # If timelimit not supplied, infer from look_back_days (heuristic)
            inferred_timelimit = timelimit
            if inferred_timelimit is None:
                if look_back_days <= 1:
                    inferred_timelimit = "d"
                elif look_back_days <= 7:
                    inferred_timelimit = "w"
                else:
                    inferred_timelimit = "m"

            with DDGS() as ddgs_client:
                results = list(
                    ddgs_client.news(
                        query=query,
                        region=region,
                        safesearch=safesearch,
                        timelimit=inferred_timelimit,
                        max_results=max_results * 3,  # fetch extra for post-filtering
                        page=1,
                        backend=backend,
                    )
                )

            filtered: List[Dict] = []
            for item in results:
                # each item may have date field as datetime or string
                published = item.get("date") or item.get("published") or item.get("timestamp")
                pub_dt = None
                if isinstance(published, datetime):
                    pub_dt = published
                elif isinstance(published, (int, float)):
                    pub_dt = datetime.utcfromtimestamp(published)
                elif isinstance(published, str):
                    # attempt multiple parses
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                        try:
                            pub_dt = datetime.strptime(published.replace("Z",""), fmt)
                            break
                        except Exception:
                            continue
                # Normalize timezone-aware to naive UTC
                if pub_dt is not None and pub_dt.tzinfo is not None:
                    pub_dt = pub_dt.astimezone(tz=None).replace(tzinfo=None)
                if pub_dt is None:
                    continue
                if not (before <= pub_dt <= curr_dt):
                    continue
                filtered.append({
                    "title": item.get("title",""),
                    "source": item.get("source",""),
                    "date": pub_dt.strftime("%Y-%m-%d %H:%M"),
                    "snippet": item.get("body") or item.get("excerpt") or "",
                    "url": item.get("url") or item.get("link") or "",
                })
                if len(filtered) >= max_results:
                    break

            json_data = {"data": filtered}
            json.dump(json_data, open(cache_file, "w"))

        if len(json_data["data"]) == 0:
            return "No news data available for this query."

        combined = ""
        for entry in json_data["data"]:
            combined += f"### {entry['title']}\nSource: {entry['source']} | Date: {entry['date']}\n{entry['snippet']}\nURL: {entry['url']}\n\n"

        header_meta = (
            f"Region: {region} | Safesearch: {safesearch} | Timelimit: {timelimit or 'inferred'} | Backend: {backend}"
        )
        return (
            f"## {query} DuckDuckGo News, from {before_str} to {curr_date}:\n"
            f"{header_meta}\n\n" + combined
        )

if __name__ == "__main__":
    service = DuckDuckGoNewsService()
    print(service.get_news("AAPL", "2025-08-25", 30, max_results=5))
