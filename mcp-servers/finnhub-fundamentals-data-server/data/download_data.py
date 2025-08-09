import datetime
import json
import os

import finnhub

finnhub_client = finnhub.Client(api_key=os.getenv("FINNHUB_API_KEY"))

for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]:
    for data_type in ["news_data", "insider_senti", "insider_trans"]:
        try:
            if data_type == "news_data":
                json_data = {
                    "data": finnhub_client.company_news(
                        ticker,
                        "2025-01-01",
                        datetime.date.today().strftime("%Y-%m-%d"),
                    )
                }

            elif data_type == "insider_senti":
                json_data = finnhub_client.stock_insider_sentiment(
                    ticker,
                    "2025-01-01",
                    datetime.date.today().strftime("%Y-%m-%d"),
                )

            elif data_type == "insider_trans":
                json_data = finnhub_client.stock_insider_transactions(
                    ticker,
                    "2025-01-01",
                    datetime.date.today().strftime("%Y-%m-%d"),
                )

            os.makedirs(f"{data_type}", exist_ok=True)
            with open(f"{data_type}/{ticker}_data_formatted.json", "w") as f:
                json.dump(json_data, f)

        except Exception as e:
            print(f"Error fetching {data_type} for {ticker}: {e}")
            continue
