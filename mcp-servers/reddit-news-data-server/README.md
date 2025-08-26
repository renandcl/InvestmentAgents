# Reddit News Data Server

This MCP server provides news data from Reddit.

## Tools

### get_reddit_news
Get news articles related to a specific company from Reddit.

## Usage

Run the server:
```bash
uv run --env-file .env main.py
```

The server will start in stdio transport mode for MCP communication.

## Environment

- Requires valid Reddit API credentials in the `.env` file as `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`