# Finnhub News Data Server

This MCP server provides access to company news data for trading agents and other applications.

## Features

- **Company News Data**: Retrieve recent news articles for a given ticker from Finnhub

## Tools

### get_finnhub_news
Get recent news articles for a company ticker within a specified look-back period (in days).

## Usage

Run the server:
```bash
uv run --env-file .env main.py
```

The server will start in stdio transport mode for MCP communication.

## Environment

- Requires a valid Finnhub API key in the `.env` file as `FINNHUB_API_KEY`
