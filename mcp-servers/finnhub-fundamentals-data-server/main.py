from mcp.server.fastmcp import FastMCP
from models import InsiderSentimentParameters, InsiderTransactionsParameters
from services import FinnhubInsiderSentimentService, FinnhubInsiderTransactionsService

mcp = FastMCP("finnhub-fundamental-data")
finnhub_insider_transactions_service = FinnhubInsiderTransactionsService()
finnhub_insider_sentiment_service = FinnhubInsiderSentimentService()


@mcp.tool()
async def get_insider_sentiment(payload: InsiderSentimentParameters) -> str:
    """
    Retrieve insider sentiment information about a company (retrieved from public SEC information) for the past 30 days

    Returns:
        str: a report of the sentiment in the past 30 days starting at curr_date
    """
    ticker = payload.ticker
    curr_date = payload.curr_date

    data_sentiment = finnhub_insider_sentiment_service.get_insider_sentiment(
        ticker, curr_date, 30
    )
    return data_sentiment


@mcp.tool()
async def get_insider_transactions(payload: InsiderTransactionsParameters) -> str:
    """
    Retrieve insider transaction information about a company (retrieved from public SEC information) for the past 30 days

    Returns:
        str: a report of the company's insider transactions/trading information in the past 30 days
    """
    ticker = payload.ticker
    curr_date = payload.curr_date

    data_trans = finnhub_insider_transactions_service.get_insider_transactions(
        ticker, curr_date, 30
    )
    return data_trans


if __name__ == "__main__":
    mcp.run(transport="stdio")
