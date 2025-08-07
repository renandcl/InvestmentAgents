# Financial Data Server

This MCP server provides access insider trading data for trading agents.

## Features

- **Insider Trading Data**: SEC insider sentiment and transaction information

## Tools

### get_finnhub_company_insider_sentiment
Get insider sentiment analysis from SEC filings for the past 30 days.

### get_finnhub_company_insider_transactions
Retrieve insider transaction data from SEC filings for the past 30 days.

## Usage

Run the server:
```bash
uv run --env-file .env main.py
```

The server will start in stdio transport mode for MCP communication.
