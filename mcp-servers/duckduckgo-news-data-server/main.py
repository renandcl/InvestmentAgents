from datetime import datetime

from mcp.server.fastmcp import FastMCP
from models import DuckDuckGoNewsParameters
from services import DuckDuckGoNewsService

mcp = FastMCP("duckduckgo-news-data")
duck_service = DuckDuckGoNewsService()


@mcp.tool()
def get_duckduckgo_news(payload: DuckDuckGoNewsParameters) -> str:
    """
    Retrieve DuckDuckGo News articles for a query within a date range.

    Returns:
        str: Markdown of news articles (title, source, date, snippet, URL).
    """
    query = payload.query
    start_date = payload.start_date
    end_date = payload.end_date

    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    look_back_days = (end_date_dt - start_date_dt).days

    return duck_service.get_news(query, end_date, look_back_days)


if __name__ == "__main__":
    mcp.run(transport="stdio")
