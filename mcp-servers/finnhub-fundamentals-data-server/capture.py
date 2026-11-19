# ruff: noqa: E402
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.providers.capture import run_cli
from runtime.providers.timecut import Record
from services import insider_sentiment_service as sentiment
from services import insider_transactions_service as transactions

SERVICES = (transactions, sentiment)


def fetch(request: dict[str, Any], output: Path) -> None:
    for service in SERVICES:
        service.fetch(request, output)


def normalize(request: dict[str, Any], raw: Path) -> list[Record]:
    return [
        record for service in SERVICES for record in service.normalize(request, raw)
    ]


def coverage(request: dict[str, Any], raw: Path) -> dict[str, dict[str, Any]]:
    entries = {service.SOURCE: service.coverage(request, raw) for service in SERVICES}
    return {
        item["date"]: {source: entries[source][item["date"]] for source in entries}
        for item in request["candidates"]
    }


if __name__ == "__main__":
    raise SystemExit(run_cli(fetch, normalize, coverage=coverage))
