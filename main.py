import asyncio

import pandas as pd

from agents.investment_manager.agent import InvestmentManager
from runtime.context import RunConfig
from runtime.errors import RunExecutionError
from runtime.lifecycle import create_run


async def run_analysis(ticker: str, date: str, **config_options):
    """Return a committed RunResult, or raise an error carrying the run identity."""
    runtime = create_run(RunConfig(ticker, date, **config_options))
    return await runtime.execute(
        InvestmentManager,
        "Execute the investment analyses.",
        "investment_manager_report",
    )


def main():
    # Configuration
    assets = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]
    start_date = "2025-08-01"
    end_date = "2025-10-01"
    period_type = "weekly"  # Options: "weekly", "biweekly", "monthly"

    print(
        f"Configuration: Assets={assets}, Start={start_date}, End={end_date}, Period={period_type}"
    )

    # Generate dates using pandas
    if period_type == "weekly":
        freq = "W-FRI"  # Weekly on Fridays
    elif period_type == "biweekly":
        freq = "2W-FRI"  # Every 2 weeks on Fridays
    elif period_type == "monthly":
        freq = "ME"  # Month End
    else:
        print(f"Unknown period type: {period_type}. Defaulting to weekly.")
        freq = "W-FRI"

    dates = (
        pd.date_range(start=start_date, end=end_date, freq=freq)
        .strftime("%Y-%m-%d")
        .tolist()
    )

    if not dates:
        print("No dates generated. Check your date range and frequency.")
        return

    print(f"Generated dates: {dates}")

    # Run analysis for each asset and date
    failures = 0
    for ticker in assets:
        for date in dates:
            try:
                result = asyncio.run(run_analysis(ticker, date))
                print(
                    f"Run {result.run_id}: {result.status}; report: {result.report_path}"
                )
            except RunExecutionError as error:
                failures += 1
                print(str(error))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
