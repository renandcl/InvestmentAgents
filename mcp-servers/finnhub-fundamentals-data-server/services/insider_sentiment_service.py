import os
from datetime import datetime

import finnhub
from dateutil.relativedelta import relativedelta

finnhub_client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))


def get_finnhub_company_insider_sentiment(
    ticker: str,
    curr_date: str,
    look_back_days: int,
):
    date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    before = date_obj - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")
    json_data = finnhub_client.stock_insider_sentiment(
        ticker,
        before,
        curr_date,
    )
    filtered_data = {}
    for entry in json_data["data"]:
        date_str = f"{entry['year']}-{entry['month']:02d}"
        if before <= date_str <= curr_date:
            filtered_data[date_str] = entry
    if len(filtered_data) == 0:
        return "No insider sentiment data available for this company."
    result_str = ""
    for date, entry in filtered_data.items():
        result_str += (
            f"### {entry['year']}-{entry['month']}:\n"
            f"Change: {entry['change']}\n"
            f"Monthly Share Purchase Ratio: {entry['mspr']}\n\n"
        )
    return (
        f"## {ticker} Insider Sentiment Data for {before} to {curr_date}:\n"
        + result_str
        + "The change field refers to the net buying/selling from all insiders' transactions. The mspr field refers to monthly share purchase ratio."
    )
