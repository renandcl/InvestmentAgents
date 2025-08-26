from datetime import datetime

from mcp.server.fastmcp import FastMCP
from models import GoogleNewsParameters
from services import GoogleNewsService

mcp = FastMCP("google-news-data")
google_news_service = GoogleNewsService()


@mcp.tool()
def get_google_news(payload: GoogleNewsParameters) -> str:
    """
    Retrieve Google News articles for a query within a date range.

    Returns:
        str: A formatted markdown string with top news articles.
    """
    query = payload.query
    start_date = payload.start_date
    end_date = payload.end_date

    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    look_back_days = (end_date_dt - start_date_dt).days

    return google_news_service.get_news(query, end_date, look_back_days)


if __name__ == "__main__":
    mcp.run(transport="stdio")
