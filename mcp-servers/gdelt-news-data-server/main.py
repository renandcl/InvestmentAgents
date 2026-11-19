# Validate host context before importing libraries that may initialize services.
# ruff: noqa: E402
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.providers.cache import provider_context

provider_context("gdelt-news-data-server")

from mcp.server.fastmcp import FastMCP

from models import GdeltNewsParameters
from services import GdeltNewsService

mcp = FastMCP("gdelt-news-data")
gdelt_service = GdeltNewsService()


@mcp.tool()
def get_gdelt_news(query: str, start_date: str, end_date: str) -> str:
    """
    Retrieve worldwide English news articles from GDELT for a query within a date range.

    Args:
        query: Query string to search for (company name or topic)
        start_date: start date in yyyy-mm-dd format, inclusive New York date
        end_date: end date in yyyy-mm-dd format, inclusive New York date

    Returns:
        str: Markdown of news articles (title, source domain, date, URL), newest first.
    """
    try:
        params = GdeltNewsParameters(
            query=query, start_date=start_date, end_date=end_date
        )
        return gdelt_service.get_news(params.query, params.start_date, params.end_date)
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
