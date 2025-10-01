from datetime import datetime

from mcp.server.fastmcp import FastMCP
from models import RedditNewsParameters
from services import RedditNewsService

mcp = FastMCP("reddit-news-data")
reddit_news_service = RedditNewsService()


@mcp.tool()
def get_reddit_news(payload: RedditNewsParameters) -> str:
    """
    Retrieve the latest news about a given stock from Reddit within a specific time frame

    Returns:
        str: A formatted text containing the latest news about the company from Reddit in a specified time frame.
    """
    ticker = payload.ticker
    start_date = payload.start_date
    end_date = payload.end_date

    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    look_back_days = (end_date_dt - start_date_dt).days

    reddit_news_result = reddit_news_service.get_news(ticker, end_date, look_back_days)

    return reddit_news_result


if __name__ == "__main__":
    # print("Starting Reddit News Data Server...")
    mcp.run(transport="stdio")
    
    # reddit_news_service = RedditNewsService()

    # payload = RedditNewsParameters(
    #     ticker="AAPL",
    #     start_date="2025-09-01",
    #     end_date="2025-10-01",
    # )
    # print(f"Payload: {payload}")
    
    # result = reddit_news_service.get_news(
    #     payload.ticker,
    #     payload.end_date,
    #     (datetime.strptime(payload.end_date, "%Y-%m-%d") -
    #     datetime.strptime(payload.start_date, "%Y-%m-%d")).days
    # )

