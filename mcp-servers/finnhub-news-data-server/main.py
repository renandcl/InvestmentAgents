from datetime import datetime

from mcp.server.fastmcp import FastMCP
from models import FinnhubNewsParameters
from services import FinnhubNewsService

mcp = FastMCP("finnhub-news-data")
finnhub_news = FinnhubNewsService()


@mcp.tool()
def get_finnhub_news(ticker: str, start_date: str, end_date: str) -> str:
    """
    Retrieve the latest news about a given stock from Finnhub within a date range

    Args:
        ticker: ticker symbol for the company
        start_date: start date in yyyy-mm-dd format
        end_date: end date in yyyy-mm-dd format

    Returns:
        str: A formatted dataframe containing news about the company within the date range from start_date to end_date
    """
    try:
        params = FinnhubNewsParameters(
            ticker=ticker, start_date=start_date, end_date=end_date
        )

        end_date_dt = datetime.strptime(params.end_date, "%Y-%m-%d")
        start_date_dt = datetime.strptime(params.start_date, "%Y-%m-%d")
        look_back_days = (end_date_dt - start_date_dt).days

        finnhub_news_result = finnhub_news.get_news(
            params.ticker, params.end_date, look_back_days
        )
        return finnhub_news_result
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
