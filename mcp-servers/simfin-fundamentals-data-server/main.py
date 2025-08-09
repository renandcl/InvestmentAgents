from mcp.server.fastmcp import FastMCP
from models import FinancialsRequest
from services import (
    get_simfin_balance_sheet,
    get_simfin_cashflow,
    get_simfin_income_statements,
)

mcp = FastMCP("simfin-financial-data")


@mcp.tool()
async def get_balance_sheet(request: FinancialsRequest) -> str:
    """
    Retrieve the most recent balance sheet of a company
    Args:
        ticker (str): ticker symbol of the company
        freq (str): reporting frequency of the company's financial history: annual / quarterly
        curr_date (str): current date you are trading at, yyyy-mm-dd
    Returns:
        str: a report of the company's most recent balance sheet
    """
    data_balance_sheet = get_simfin_balance_sheet(
        request.ticker, request.freq, request.curr_date
    )
    return data_balance_sheet


@mcp.tool()
async def get_cashflow(request: FinancialsRequest) -> str:
    """
    Retrieve the most recent cash flow statement of a company
    Args:
        ticker (str): ticker symbol of the company
        freq (str): reporting frequency of the company's financial history: annual / quarterly
        curr_date (str): current date you are trading at, yyyy-mm-dd
    Returns:
        str: a report of the company's most recent cash flow statement
    """
    data_cashflow = get_simfin_cashflow(request.ticker, request.freq, request.curr_date)
    return data_cashflow


@mcp.tool()
async def get_income_statements(request: FinancialsRequest) -> str:
    """
    Retrieve the most recent income statement of a company
    Args:
        ticker (str): ticker symbol of the company
        freq (str): reporting frequency of the company's financial history: annual / quarterly
        curr_date (str): current date you are trading at, yyyy-mm-dd
    Returns:
        str: a report of the company's most recent income statement
    """
    data_income_stmt = get_simfin_income_statements(
        request.ticker, request.freq, request.curr_date
    )
    return data_income_stmt


if __name__ == "__main__":
    mcp.run(transport="stdio")
