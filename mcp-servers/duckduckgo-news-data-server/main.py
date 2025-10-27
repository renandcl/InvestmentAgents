from datetime import datetime

from mcp.server.fastmcp import FastMCP
from models import DuckDuckGoNewsParameters
from services import DuckDuckGoNewsService

mcp = FastMCP("duckduckgo-news-data")
duck_service = DuckDuckGoNewsService()


@mcp.tool()
def get_duckduckgo_news(query: str, start_date: str, end_date: str) -> str:
    """
    Retrieve DuckDuckGo News articles for a query within a date range.
    
    Args:
        query: Query string to search for (company name or topic)
        start_date: start date in yyyy-mm-dd format
        end_date: end date in yyyy-mm-dd format

    Returns:
        str: Markdown of news articles (title, source, date, snippet, URL).
    """
    try:
        params = DuckDuckGoNewsParameters(query=query, start_date=start_date, end_date=end_date)
        
        end_date_dt = datetime.strptime(params.end_date, "%Y-%m-%d")
        start_date_dt = datetime.strptime(params.start_date, "%Y-%m-%d")
        look_back_days = (end_date_dt - start_date_dt).days

        return duck_service.get_news(params.query, params.end_date, look_back_days)
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
