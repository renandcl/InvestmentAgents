from typing import Annotated
from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone
import os

import finnhub

finnhub_client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))


def get_finnhub_news(
    ticker: Annotated[
        str,
        "Search query of a company's, e.g. 'AAPL, TSM, etc.",
    ],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "how many days to look back"],
):
    """
    Retrieve news about a company within a time frame

    Args
        ticker (str): ticker for the company you are interested in
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns
        str: dataframe containing the news of the company in the time frame

    """

    start_date = datetime.strptime(curr_date, "%Y-%m-%d")
    before = start_date - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")
    json_data = {"data": finnhub_client.company_news(ticker, before, curr_date)}

    if len(json_data["data"]) == 0:
        return "No news data available for this company."

    combined_result = ""
    for entry in json_data["data"]:
        headline = entry.get("headline", "")
        summary = entry.get("summary", "")
        source = entry.get("source", "")
        url = entry.get("url", "")
        dt = entry.get("datetime", None)
        date_str = (
            datetime.fromtimestamp(dt, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            if dt
            else ""
        )
        combined_result += (
            f"### {headline} ({date_str})\nSource: {source}\n{summary}\nURL: {url}\n\n"
        )

    return f"## {ticker} News, from {before} to {curr_date}:\n" + str(combined_result)


def get_finnhub_company_insider_sentiment(
    ticker: Annotated[str, "ticker symbol for the company"],
    curr_date: Annotated[
        str,
        "current date of you are trading at, yyyy-mm-dd",
    ],
    look_back_days: Annotated[int, "number of days to look back"],
):
    """
    Retrieve insider sentiment about a company (retrieved from public SEC information) for the past 15 days
    Args:
        ticker (str): ticker symbol of the company
        curr_date (str): current date you are trading on, yyyy-mm-dd
    Returns:
        str: a report of the sentiment in the past 15 days starting at curr_date
    """

    date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    before = date_obj - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")
    json_data = finnhub_client.stock_insider_sentiment(
        ticker,
        before,
        curr_date,
    )

    # filter keys (date, str in format YYYY-MM-DD) by the date range (str, str in format YYYY-MM-DD)
    filtered_data = {}
    for entry in json_data["data"]:
        date_str = f"{entry['year']}-{entry['month']:02d}"
        if before <= date_str <= curr_date:
            filtered_data[date_str] = entry

    if len(filtered_data) == 0:
        return "No insider sentiment data available for this company."

    result_str = ""
    for date, entry in filtered_data.items():
        # entry is a dict with keys: symbol, year, month, change, mspr
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


def get_finnhub_company_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[
        str,
        "current date you are trading at, yyyy-mm-dd",
    ],
    look_back_days: Annotated[int, "how many days to look back"],
):
    """
    Retrieve insider transcaction information about a company (retrieved from public SEC information) for the past 15 days
    Args:
        ticker (str): ticker symbol of the company
        curr_date (str): current date you are trading at, yyyy-mm-dd
    Returns:
        str: a report of the company's insider transaction/trading informtaion in the past 15 days
    """

    date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    before = date_obj - relativedelta(days=look_back_days)
    before = before.strftime("%Y-%m-%d")
    json_data = finnhub_client.stock_insider_transactions(
        ticker,
        before,
        curr_date,
    )

    if len(json_data.get("data", [])) == 0:
        return "No insider transaction data available for this company."

    result_str = ""
    # The API returns a dict with a "data" key containing a list of transactions.
    seen_ids = set()
    for entry in json_data.get("data", []):
        entry_id = entry.get("id")
        if entry_id and entry_id not in seen_ids:
            result_str += (
                f"### Filing Date: {entry.get('filingDate', '')}, Insider: {entry.get('name', '')}\n"
                f"Change: {entry.get('change', '')}\n"
                f"Shares: {entry.get('share', '')}\n"
                f"Transaction Price: {entry.get('transactionPrice', '')}\n"
                f"Transaction Code: {entry.get('transactionCode', '')}\n"
                f"Transaction Date: {entry.get('transactionDate', '')}\n"
                f"Symbol: {entry.get('symbol', '')}\n"
                f"Is Derivative: {entry.get('isDerivative', '')}\n"
                f"Currency: {entry.get('currency', '')}\n"
                f"Source: {entry.get('source', '')}\n"
                f"SEC Filing ID: {entry_id}\n\n"
            )
            seen_ids.add(entry_id)

    return (
        f"## {ticker} insider transactions from {before} to {curr_date}:\n"
        + result_str
        + "The change field reflects the variation in share count—here a negative number indicates a reduction in holdings—while share specifies the total number of shares involved. The transactionPrice denotes the per-share price at which the trade was executed, and transactionDate marks when the transaction occurred. The name field identifies the insider making the trade, and transactionCode (e.g., S for sale) clarifies the nature of the transaction. FilingDate records when the transaction was officially reported, and the unique id links to the specific SEC filing, as indicated by the source. Additionally, the symbol ties the transaction to a particular company, isDerivative flags whether the trade involves derivative securities, and currency notes the currency context of the transaction."
    )


if __name__ == "__main__":
    data = get_finnhub_news("AAPL", "2025-08-05", 30)
    print(data)
    data = get_finnhub_company_insider_sentiment("AAPL", "2025-07-01", 30)
    print(data)
    data = get_finnhub_company_insider_transactions("META", "2025-08-05", 30)
    print(data)
