from datetime import datetime

from mcp.server.fastmcp import FastMCP
from models import RedditNewsParameters
from services import RedditNewsService

mcp = FastMCP("reddit-news-data")
reddit_news_service = RedditNewsService()


@mcp.tool()
def get_reddit_news(ticker: str, start_date: str, end_date: str) -> str:
    """
    Retrieve the latest news about a given stock from Reddit within a specific time frame
    
    Args:
        ticker: ticker symbol for the company
        start_date: start date in yyyy-mm-dd format
        end_date: end date in yyyy-mm-dd format

    Returns:
        str: A formatted text containing the latest news about the company from Reddit in a specified time frame.
    """
    try:
        params = RedditNewsParameters(ticker=ticker, start_date=start_date, end_date=end_date)
        
        end_date_dt = datetime.strptime(params.end_date, "%Y-%m-%d")
        start_date_dt = datetime.strptime(params.start_date, "%Y-%m-%d")
        look_back_days = (end_date_dt - start_date_dt).days

        reddit_news_result = reddit_news_service.get_news(params.ticker, params.end_date, look_back_days)
        return reddit_news_result
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
