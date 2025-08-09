import os
from typing import Annotated

import pandas as pd

file_path = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(file_path, "../data")


def get_simfin_cashflow(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[
        str,
        "reporting frequency of the company's financial history: annual / quarterly",
    ],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
):
    data_path = os.path.join(
        DATA_DIR,
        f"us-cashflow-{freq}.csv",
    )
    df = pd.read_csv(data_path, sep=";")
    df["Report Date"] = pd.to_datetime(df["Report Date"], utc=True).dt.normalize()
    df["Publish Date"] = pd.to_datetime(df["Publish Date"], utc=True).dt.normalize()
    curr_date_dt = pd.to_datetime(curr_date, utc=True).normalize()
    filtered_df = df[(df["Ticker"] == ticker) & (df["Publish Date"] <= curr_date_dt)]
    if filtered_df.empty:
        print("No cash flow statement available before the given current date.")
        return ""
    latest_cash_flow = filtered_df.loc[filtered_df["Publish Date"].idxmax()]
    latest_cash_flow = latest_cash_flow.drop("SimFinId")
    return (
        f"## {freq} cash flow statement for {ticker} released on {str(latest_cash_flow['Publish Date'])[0:10]}: \n"
        + str(latest_cash_flow)
        + "\n\nThis includes metadata like reporting dates and currency, share details, and a breakdown of cash movements. Operating activities show cash generated from core business operations, including net income adjustments for non-cash items and working capital changes. Investing activities cover asset acquisitions/disposals and investments. Financing activities include debt transactions, equity issuances/repurchases, and dividend payments. The net change in cash represents the overall increase or decrease in the company's cash position during the reporting period."
    )
