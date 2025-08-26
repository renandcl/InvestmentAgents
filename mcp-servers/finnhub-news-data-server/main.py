from datetime import datetime

from mcp.server.fastmcp import FastMCP
from models import FinnhubNewsParameters
from services import FinnhubNewsService

mcp = FastMCP("finnhub-news-data")
finnhub_news = FinnhubNewsService()


@mcp.tool()
def get_finnhub_news(payload: FinnhubNewsParameters):
    """
    Retrieve the latest news about a given stock from Finnhub within a date range

    Returns:
        str: A formatted dataframe containing news about the company within the date range from start_date to end_date
    """
    ticker = payload.ticker
    start_date = payload.start_date
    end_date = payload.end_date

    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
    look_back_days = (end_date_dt - start_date_dt).days

    finnhub_news_result = finnhub_news.get_news(ticker, end_date, look_back_days)

    return finnhub_news_result


if __name__ == "__main__":
    mcp.run(transport="stdio")
