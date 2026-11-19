# EDGAR Fundamentals Data Server

Captures balance sheets, cash flows and income statements from SEC EDGAR
[XBRL company facts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) for the frozen
study dataset ([spec 006](../../specs/006-time-cut-dataset/spec.md)). SEC asks automated clients to identify
themselves, so copy `.env.example` to `.env` and set `SEC_USER_AGENT` to a name and contact address.

`capture.py fetch` stores the company facts once per ticker. `capture.py normalize` turns each 10-K and 10-Q into
`edgar_balance`, `edgar_cashflow` and `edgar_income` records, public from the filing date. The MCP tools that
serve the frozen copy (`get_edgar_balance_sheet`, `get_edgar_cashflow`, `get_edgar_income_statement`) arrive in
PR 8 and replace the SimFin server.
