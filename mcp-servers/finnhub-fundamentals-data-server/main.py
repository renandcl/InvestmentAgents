from mcp.server.fastmcp import FastMCP
from models import (
    InsiderSentimentRequest,
    InsiderTransactionsRequest,
)
import services

mcp = FastMCP("finnhub-financial-data")


@mcp.tool()
async def get_finnhub_company_insider_sentiment(
    request: InsiderSentimentRequest,
) -> str:
    """
    Retrieve insider sentiment information about a company (retrieved from public SEC information) for the past 30 days
    Args:
        ticker (str): ticker symbol of the company
        curr_date (str): current date you are trading at, yyyy-mm-dd
    Returns:
        str: a report of the sentiment in the past 30 days starting at curr_date
    """
    data_sentiment = services.get_finnhub_company_insider_sentiment(
        request.ticker, request.curr_date, 30
    )
    return data_sentiment


@mcp.tool()
async def get_finnhub_company_insider_transactions(
    request: InsiderTransactionsRequest,
) -> str:
    """
    Retrieve insider transaction information about a company (retrieved from public SEC information) for the past 30 days
    Args:
        ticker (str): ticker symbol of the company
        curr_date (str): current date you are trading at, yyyy-mm-dd
    Returns:
        str: a report of the company's insider transactions/trading information in the past 30 days
    """
    data_trans = services.get_finnhub_company_insider_transactions(
        request.ticker, request.curr_date, 30
    )
    return data_trans


if __name__ == "__main__":
    mcp.run(transport="stdio")
