import os
from typing import Annotated

import pandas as pd

file_path = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(file_path, "../data")


def get_simfin_income_statements(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[
        str,
        "reporting frequency of the company's financial history: annual / quarterly",
    ],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
):
    data_path = os.path.join(
        DATA_DIR,
        f"us-income-{freq}.csv",
    )
    df = pd.read_csv(data_path, sep=";")
    df["Report Date"] = pd.to_datetime(df["Report Date"], utc=True).dt.normalize()
    df["Publish Date"] = pd.to_datetime(df["Publish Date"], utc=True).dt.normalize()
    curr_date_dt = pd.to_datetime(curr_date, utc=True).normalize()
    filtered_df = df[(df["Ticker"] == ticker) & (df["Publish Date"] <= curr_date_dt)]
    if filtered_df.empty:
        print("No income statement available before the given current date.")
        return ""
    latest_income = filtered_df.loc[filtered_df["Publish Date"].idxmax()]
    latest_income = latest_income.drop("SimFinId")
    return (
        f"## {freq} income statement for {ticker} released on {str(latest_income['Publish Date'])[0:10]}: \n"
        + str(latest_income)
        + "\n\nThis includes metadata like reporting dates and currency, share details, and a comprehensive breakdown of the company's financial performance. Starting with Revenue, it shows Cost of Revenue and resulting Gross Profit. Operating Expenses are detailed, including SG&A, R&D, and Depreciation. The statement then shows Operating Income, followed by non-operating items and Interest Expense, leading to Pretax Income. After accounting for Income Tax and any Extraordinary items, it concludes with Net Income, representing the company's bottom-line profit or loss for the period."
    )
