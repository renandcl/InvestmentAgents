from mcp.server.fastmcp import FastMCP
from models import SimfinFinancialsParameters
from services import (
    get_simfin_balance_sheet,
    get_simfin_cashflow,
    get_simfin_income_statements,
)

mcp = FastMCP("simfin-financial-data")


@mcp.tool()
async def get_balance_sheet(payload: SimfinFinancialsParameters) -> str:
    """
    Retrieve the most recent balance sheet of a company
    
    Returns:
        str: a report of the company's most recent balance sheet
    """
    ticker = payload.ticker
    freq = payload.freq
    curr_date = payload.curr_date

    data_balance_sheet = get_simfin_balance_sheet(
        ticker, freq, curr_date
    )
    return data_balance_sheet


@mcp.tool()
async def get_cashflow(payload: SimfinFinancialsParameters) -> str:
    """
    Retrieve the most recent cash flow statement of a company

    Returns:
        str: a report of the company's most recent cash flow statement
    """
    ticker = payload.ticker
    freq = payload.freq
    curr_date = payload.curr_date

    data_cashflow = get_simfin_cashflow(
        ticker, freq, curr_date
    )
    return data_cashflow

@mcp.tool()
async def get_income_statements(payload: SimfinFinancialsParameters) -> str:
    """
    Retrieve the most recent income statement of a company
    
    Returns:
        str: a report of the company's most recent income statement
    """
    ticker = payload.ticker
    freq = payload.freq
    curr_date = payload.curr_date

    data_income_stmt = get_simfin_income_statements(
        ticker, freq, curr_date
    )
    return data_income_stmt


if __name__ == "__main__":
    mcp.run(transport="stdio")
