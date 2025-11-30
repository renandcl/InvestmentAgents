import asyncio
import json
import os

import pandas as pd

from agents.investment_manager.agent import InvestmentManager
from utils.report import generate_markdown_report


async def run_analysis(ticker: str, date: str):
    """
    Runs the investment analysis for a specific ticker and date.
    """
    print(f"--- Starting analysis for {ticker} on {date} ---")

    # Update shared_document.json with the current context
    shared_doc_path = os.path.abspath("data/shared_document.json")

    # Ensure data directory exists
    os.makedirs(os.path.dirname(shared_doc_path), exist_ok=True)

    # Initialize shared document if it doesn't exist or update it
    initial_data = {"ticker": ticker, "current_date": date}
    with open(shared_doc_path, "w") as f:
        json.dump(initial_data, f)

    # Initialize and run the Investment Manager
    # We create a new instance for each run to ensure a fresh session
    investment_manager = InvestmentManager()
    prompt = "Execute the investment analyses."

    try:
        response = await investment_manager.execute_complete_workflow(prompt)
        print(f"Analysis finished for {ticker} on {date}.")
        print(f"Response: {response}")

        # Generate report
        report_filename = f"report_{ticker}_{date}.md"
        report_path = os.path.join("reports", report_filename)
        generate_markdown_report(shared_doc_path, report_path)

    except Exception as e:
        print(f"An error occurred during analysis for {ticker} on {date}: {e}")


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
    for ticker in assets:
        for date in dates:
            asyncio.run(run_analysis(ticker, date))


if __name__ == "__main__":
    main()
