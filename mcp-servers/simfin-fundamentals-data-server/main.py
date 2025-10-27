from mcp.server.fastmcp import FastMCP
from models import SimfinFinancialsParameters
from services import (
    get_simfin_balance_sheet,
    get_simfin_cashflow,
    get_simfin_income_statements,
)

mcp = FastMCP("simfin-financial-data")


@mcp.tool()
async def get_balance_sheet(ticker: str, freq: str, curr_date: str) -> str:
    """
    Retrieve the most recent balance sheet of a company
    
    Args:
        ticker: ticker symbol
        freq: reporting frequency (annual/quarterly)
        curr_date: current date you are trading at (yyyy-mm-dd)

    Returns:
        str: a report of the company's most recent balance sheet
    """
    try:
        params = SimfinFinancialsParameters(ticker=ticker, freq=freq, curr_date=curr_date)
        data_balance_sheet = get_simfin_balance_sheet(params.ticker, params.freq, params.curr_date)
        return data_balance_sheet
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_cashflow(ticker: str, freq: str, curr_date: str) -> str:
    """
    Retrieve the most recent cash flow statement of a company
    
    Args:
        ticker: ticker symbol
        freq: reporting frequency (annual/quarterly)
        curr_date: current date you are trading at (yyyy-mm-dd)

    Returns:
        str: a report of the company's most recent cash flow statement
    """
    try:
        params = SimfinFinancialsParameters(ticker=ticker, freq=freq, curr_date=curr_date)
        data_cashflow = get_simfin_cashflow(params.ticker, params.freq, params.curr_date)
        return data_cashflow
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_income_statements(ticker: str, freq: str, curr_date: str) -> str:
    """
    Retrieve the most recent income statement of a company
    
    Args:
        ticker: ticker symbol
        freq: reporting frequency (annual/quarterly)
        curr_date: current date you are trading at (yyyy-mm-dd)

    Returns:
        str: a report of the company's most recent income statement
    """
    try:
        params = SimfinFinancialsParameters(ticker=ticker, freq=freq, curr_date=curr_date)
        data_income_stmt = get_simfin_income_statements(params.ticker, params.freq, params.curr_date)
        return data_income_stmt
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
