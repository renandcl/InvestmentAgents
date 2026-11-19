"""SEC EDGAR financial statements for the study dataset (spec 006)."""

from __future__ import annotations

import os
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from runtime.providers.capture import read_slice, slice_finished, write_slice
from runtime.providers.timecut import (
    NEW_YORK,
    Record,
    parse_instant,
    public_at_from_date,
)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FACTS_SLICE = "companyfacts"
FRESHNESS_DAYS = 120
FORMS = {"10-K": "annual", "10-Q": "quarterly"}
QUARTER_DAYS = 91
SPAN_DAYS = {"Q1": 91, "Q2": 182, "Q3": 273, "FY": 364}
SPAN_TOLERANCE = 20
BALANCE = (
    "CashAndCashEquivalentsAtCarryingValue",
    "MarketableSecuritiesCurrent",
    "AccountsReceivableNetCurrent",
    "InventoryNet",
    "AssetsCurrent",
    "PropertyPlantAndEquipmentNet",
    "Goodwill",
    "Assets",
    "AccountsPayableCurrent",
    "LiabilitiesCurrent",
    "LongTermDebtNoncurrent",
    "Liabilities",
    "RetainedEarningsAccumulatedDeficit",
    "StockholdersEquity",
    "LiabilitiesAndStockholdersEquity",
)
INCOME = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "GrossProfit",
    "ResearchAndDevelopmentExpense",
    "SellingGeneralAndAdministrativeExpense",
    "OperatingExpenses",
    "OperatingIncomeLoss",
    "NonoperatingIncomeExpense",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeTaxExpenseBenefit",
    "NetIncomeLoss",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
)
CASHFLOW = (
    "NetIncomeLoss",
    "DepreciationDepletionAndAmortization",
    "ShareBasedCompensation",
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "NetCashProvidedByUsedInInvestingActivities",
    "PaymentsForRepurchaseOfCommonStock",
    "PaymentsOfDividends",
    "NetCashProvidedByUsedInFinancingActivities",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
)
STATEMENTS = {
    "edgar_balance": BALANCE,
    "edgar_cashflow": CASHFLOW,
    "edgar_income": INCOME,
}


def fetch(request: dict[str, Any], output: Path) -> None:
    """Store the company's XBRL facts once; SEC asks for a contact User-Agent."""
    if slice_finished(output, FACTS_SLICE):
        return
    headers = {"User-Agent": os.environ["SEC_USER_AGENT"]}
    listing = requests.get(TICKERS_URL, headers=headers, timeout=60)
    listing.raise_for_status()
    cik = next(
        item["cik_str"]
        for item in listing.json().values()
        if item["ticker"] == request["ticker"]
    )
    facts = requests.get(FACTS_URL.format(cik=cik), headers=headers, timeout=60)
    facts.raise_for_status()
    write_slice(output, FACTS_SLICE, facts.json())


def _facts(raw: Path) -> dict[str, list[dict[str, Any]]]:
    gaap = read_slice(raw, FACTS_SLICE)["facts"].get("us-gaap", {})
    return {
        concept: next(iter(gaap[concept]["units"].values()))
        for concepts in STATEMENTS.values()
        for concept in concepts
        if concept in gaap
    }


def _filings(facts: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], int]:
    filings: dict[str, dict[str, Any]] = {}
    invalid = set()
    for rows in facts.values():
        for row in rows:
            if row.get("form") not in FORMS:
                continue
            try:
                date.fromisoformat(row.get("filed", ""))
            except ValueError:
                invalid.add(row["accn"])
                continue
            filing = filings.setdefault(row["accn"], {**row})
            filing["end"] = max(filing["end"], row["end"])
    return {key: value for key, value in filings.items() if key not in invalid}, len(
        invalid
    )


def _duration(row: dict[str, Any]) -> int:
    return (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days


def _statement(
    facts: dict[str, list[dict[str, Any]]],
    concepts: tuple[str, ...],
    accession: str,
    filing: dict[str, Any],
    span_days: int | None,
) -> dict[str, Any]:
    """One filing's own period: every duration fact shares one start."""
    rows = {
        concept: [
            row
            for row in facts.get(concept, [])
            if row["accn"] == accession and row["end"] == filing["end"]
        ]
        for concept in concepts
    }
    starts = Counter(
        row["start"]
        for found in rows.values()
        for row in found
        if "start" in row
        and span_days is not None
        and abs(_duration(row) - span_days) <= SPAN_TOLERANCE
    )
    start = min(starts, key=lambda day: (-starts[day], day)) if starts else None
    values: dict[str, Any] = {"Period Start": start} if start else {}
    for concept, found in rows.items():
        match = [row for row in found if row.get("start") == start]
        if match:
            values[concept] = match[0]["val"]
    return values if len(values) > bool(start) else {}


def _records(raw: Path) -> tuple[list[Record], int]:
    facts = _facts(raw)
    filings, dropped = _filings(facts)
    records = []
    for accession, filing in sorted(filings.items()):
        freq = FORMS[filing["form"]]
        for source, concepts in STATEMENTS.items():
            # 10-Q income is quarterly; cash flow and 10-Ks use the fiscal year to date.
            span = SPAN_DAYS.get(filing.get("fp"))
            if freq == "quarterly" and source == "edgar_income":
                span = QUARTER_DAYS
            if source == "edgar_balance":
                span = None
            values = _statement(facts, concepts, accession, filing, span)
            if not values:
                continue
            payload = {
                "Form": filing["form"],
                "Fiscal Year": filing.get("fy"),
                "Fiscal Period": filing.get("fp"),
                "Report Date": filing["end"],
                "Publish Date": filing["filed"],
                "Accession": accession,
                **values,
            }
            public_at = public_at_from_date(date.fromisoformat(filing["filed"]))
            identifier = f"{freq}|{filing['end']}|{filing['filed']}"
            records.append(Record(identifier, public_at, source, payload))
    return records, dropped


def normalize(request: dict[str, Any], raw: Path) -> list[Record]:
    return _records(raw)[0]


def coverage(request: dict[str, Any], raw: Path) -> dict[str, dict[str, Any]]:
    """The latest admitted statement must be at most 120 days before the cutoff."""
    records, dropped = _records(raw)
    entries: dict[str, dict[str, Any]] = {}
    for candidate in request["candidates"]:
        cutoff = parse_instant(candidate["cutoff"])
        required = cutoff.astimezone(NEW_YORK) - timedelta(days=FRESHNESS_DAYS)
        entries[candidate["date"]] = {}
        for source in STATEMENTS:
            published = sorted(
                record.payload["Publish Date"]
                for record in records
                if record.source == source and record.public_at <= cutoff
            )
            latest = published[-1] if published else None
            entries[candidate["date"]][source] = {
                "reachable": True,
                "records": len(published),
                "truncated": False,
                "earliest_reached": published[0] if published else None,
                "latest_reached": latest,
                "required_start": required.date().isoformat(),
                "coverage_rule_met": latest is not None
                and latest >= required.date().isoformat(),
                "dropped_rows": dropped,
            }
    return entries
