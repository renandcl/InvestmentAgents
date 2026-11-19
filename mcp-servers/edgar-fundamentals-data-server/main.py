# Validate host context before importing libraries that may initialize services.
# ruff: noqa: E402
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.providers.cache import provider_context

provider_context("edgar-fundamentals-data-server")

from mcp.server.fastmcp import FastMCP

from models import EdgarFinancialsParameters
from services import EdgarStatementsService

mcp = FastMCP("edgar-financial-data")
edgar_statements_service = EdgarStatementsService()


def statement(source: str, ticker: str, freq: str, curr_date: str) -> str:
    try:
        params = EdgarFinancialsParameters(
            ticker=ticker, freq=freq, curr_date=curr_date
        )
        return edgar_statements_service.get_statement(
            source, params.ticker, params.freq, params.curr_date
        )
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_edgar_balance_sheet(ticker: str, freq: str, curr_date: str) -> str:
    """
    Retrieve the most recent balance sheet a company filed with the SEC

    Args:
        ticker: ticker symbol
        freq: reporting frequency (annual/quarterly)
        curr_date: current date you are trading at (yyyy-mm-dd)

    Returns:
        str: a report of the company's most recent balance sheet
    """
    return statement("edgar_balance", ticker, freq, curr_date)


@mcp.tool()
async def get_edgar_cashflow(ticker: str, freq: str, curr_date: str) -> str:
    """
    Retrieve the most recent cash flow statement a company filed with the SEC

    Args:
        ticker: ticker symbol
        freq: reporting frequency (annual/quarterly)
        curr_date: current date you are trading at (yyyy-mm-dd)

    Returns:
        str: a report of the company's most recent cash flow statement
    """
    return statement("edgar_cashflow", ticker, freq, curr_date)


@mcp.tool()
async def get_edgar_income_statement(ticker: str, freq: str, curr_date: str) -> str:
    """
    Retrieve the most recent income statement a company filed with the SEC

    Args:
        ticker: ticker symbol
        freq: reporting frequency (annual/quarterly)
        curr_date: current date you are trading at (yyyy-mm-dd)

    Returns:
        str: a report of the company's most recent income statement
    """
    return statement("edgar_income", ticker, freq, curr_date)


if __name__ == "__main__":
    mcp.run(transport="stdio")
