import os
from typing import Annotated

import pandas as pd

file_path = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(file_path, "../data")


def get_simfin_balance_sheet(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[
        str,
        "reporting frequency of the company's financial history: annual / quarterly",
    ],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
):
    """
    Retrieve the balance sheet for a specific company from SimFin.
    Args:
        ticker (str): The ticker symbol of the company.
        freq (str): The reporting frequency (annual or quarterly).
        curr_date (str): The current date in yyyy-mm-dd format.
    Returns:
        str: The balance sheet information for the specified company.
    """
    data_path = os.path.join(
        DATA_DIR,
        f"us-balance-{freq}.csv",
    )
    df = pd.read_csv(data_path, sep=";")
    df["Report Date"] = pd.to_datetime(df["Report Date"], utc=True).dt.normalize()
    df["Publish Date"] = pd.to_datetime(df["Publish Date"], utc=True).dt.normalize()
    curr_date_dt = pd.to_datetime(curr_date, utc=True).normalize()
    filtered_df = df[(df["Ticker"] == ticker) & (df["Publish Date"] <= curr_date_dt)]
    if filtered_df.empty:
        print("No balance sheet available before the given current date.")
        return ""
    latest_balance_sheet = filtered_df.loc[filtered_df["Publish Date"].idxmax()]
    latest_balance_sheet = latest_balance_sheet.drop("SimFinId")
    return (
        f"## {freq} balance sheet for {ticker} released on {str(latest_balance_sheet['Publish Date'])[0:10]}: \n"
        + str(latest_balance_sheet)
        + "\n\nThis includes metadata like reporting dates and currency, share details, and a breakdown of assets, liabilities, and equity. Assets are grouped as current (liquid items like cash and receivables) and noncurrent (long-term investments and property). Liabilities are split between short-term obligations and long-term debts, while equity reflects shareholder funds such as paid-in capital and retained earnings. Together, these components ensure that total assets equal the sum of liabilities and equity."
    )
