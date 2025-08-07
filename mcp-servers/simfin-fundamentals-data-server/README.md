# Financial Data Server

This MCP server provides access to financial statements for trading agents.

## Features

- **Financial Statements**: Balance sheets, cash flow statements, and income statements

## Tools

### get_simfin_balance_sheet
Get the most recent balance sheet for a company (annual or quarterly).

### get_simfin_cashflow
Retrieve the most recent cash flow statement for a company.

### get_simfin_income_stmt
Get the most recent income statement for a company.

## Usage

Get data:

```python
cd data
uv run --env-file .venv download_data.py
```

MCP Server:

```bash
uv run main.py
```

The server will start in stdio transport mode for MCP communication.
