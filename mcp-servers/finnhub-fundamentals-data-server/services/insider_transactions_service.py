import os
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta

import finnhub

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

class FinnhubInsiderTransactionsService:
    def __init__(self):
        self.client = finnhub.Client(api_key=FINNHUB_API_KEY)

    def get_insider_transactions(
        self,
        ticker: str,
        curr_date: str,
        look_back_days: int,
    ):
        date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
        before = date_obj - relativedelta(days=look_back_days)
        before = before.strftime("%Y-%m-%d")

        file_path = f"data/insider_transactions_data/finnhub_insider_transactions_{ticker}_{before}_{curr_date}.json"

        if os.path.exists(file_path):
            json_data = json.load(open(file_path, "r"))
        else:

            json_data = self.client.stock_insider_transactions(
                ticker,
                before,
                curr_date,
            )

            os.makedirs("data/insider_transactions_data", exist_ok=True)
            json.dump(json_data, open(file_path, "w"))
            
        if len(json_data.get("data", [])) == 0:
            return "No insider transaction data available for this company."
        
        result_str = ""
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
