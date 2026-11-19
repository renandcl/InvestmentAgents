# EDGAR Fundamentals Data Server

Serves balance sheets, cash flows and income statements from SEC EDGAR
[XBRL company facts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces). SEC asks
automated clients to identify themselves, so copy `.env.example` to `.env` and set `SEC_USER_AGENT` to a name and
contact address.

## Tools

### get_edgar_balance_sheet
### get_edgar_cashflow
### get_edgar_income_statement

Each takes `ticker`, `freq` (`annual` for 10-K, `quarterly` for 10-Q) and `curr_date`, and returns the latest
statement filed on or before `curr_date`.

## Study dataset capture

For the frozen study dataset ([spec 006](../../specs/006-time-cut-dataset/spec.md)), `capture.py fetch` stores the
company facts once per ticker and `capture.py normalize` turns each filing into `edgar_balance`, `edgar_cashflow` and
`edgar_income` records, public from the filing date.
