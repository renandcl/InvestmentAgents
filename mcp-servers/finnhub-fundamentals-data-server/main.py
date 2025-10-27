from mcp.server.fastmcp import FastMCP
from models import InsiderSentimentParameters, InsiderTransactionsParameters
from services import FinnhubInsiderSentimentService, FinnhubInsiderTransactionsService

mcp = FastMCP("finnhub-fundamental-data")
finnhub_insider_transactions_service = FinnhubInsiderTransactionsService()
finnhub_insider_sentiment_service = FinnhubInsiderSentimentService()


@mcp.tool()
async def get_insider_sentiment(ticker: str, curr_date: str) -> str:
    """
    Retrieve insider sentiment information about a company (retrieved from public SEC information) for the past 30 days
    
    Args:
        ticker: ticker symbol for the company
        curr_date: current date of you are trading at (yyyy-mm-dd)

    Returns:
        str: a report of the sentiment in the past 30 days starting at curr_date
    """
    try:
        params = InsiderSentimentParameters(ticker=ticker, curr_date=curr_date)
        data_sentiment = finnhub_insider_sentiment_service.get_insider_sentiment(
            params.ticker, params.curr_date, 30
        )
        return data_sentiment
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_insider_transactions(ticker: str, curr_date: str) -> str:
    """
    Retrieve insider transaction information about a company (retrieved from public SEC information) for the past 30 days
    
    Args:
        ticker: ticker symbol
        curr_date: current date you are trading at (yyyy-mm-dd)

    Returns:
        str: a report of the company's insider transactions/trading information in the past 30 days
    """
    try:
        params = InsiderTransactionsParameters(ticker=ticker, curr_date=curr_date)
        data_trans = finnhub_insider_transactions_service.get_insider_transactions(
            params.ticker, params.curr_date, 30
        )
        return data_trans
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
