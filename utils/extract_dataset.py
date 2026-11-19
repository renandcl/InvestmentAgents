"""Capture raw vendor data once and build frozen study datasets (spec 006)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from runtime.core.context import REPO_ROOT, identifier
from runtime.providers.capture import record_from_dict, record_to_dict
from runtime.providers.timecut import (
    FRIDAY,
    NEW_YORK,
    Record,
    admit,
    cutoff_for,
    format_instant,
    last_admitted_date,
    parse_instant,
    study_dates,
)
from runtime.store.artifacts import hash_file

TICKERS = ("AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA")
MARKET_CLOSE = time(16, 0)
DATA_ROOT = REPO_ROOT / "data"
PURGED_MARKER = "purged.json"
UNREACHABLE = {"reachable": False, "coverage_rule_met": False}
VENDOR_KEYS = ("FINNHUB_API_KEY", "SIMFIN_API_KEY", "SEC_USER_AGENT")
VENDOR_KEY_PREFIXES = ("REDDIT_",)


@dataclass(frozen=True)
class Provider:
    name: str
    server: str
    sources: tuple[str, ...]
    env_file: bool = False


MARKET = Provider("yfinance", "yfin-market-data-server", ("prices",))
STATEMENTS = Provider(
    "edgar",
    "simfin-fundamentals-data-server",
    ("edgar_balance", "edgar_cashflow", "edgar_income"),
    env_file=True,
)
INSIDERS = Provider(
    "finnhub_fundamentals",
    "finnhub-fundamentals-data-server",
    ("insider_transactions", "insider_sentiment"),
    env_file=True,
)
CAPTURE_PROVIDERS = (MARKET, STATEMENTS, INSIDERS)
LOOKBACK_DAYS: dict[str, int | None] = {
    "prices": None,
    "edgar_balance": None,
    "edgar_cashflow": None,
    "edgar_income": None,
    "insider_transactions": 30,
    "insider_sentiment": 100,
}


def short_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def copy_key(ticker: str, day: str) -> str:
    return short_key(f"{ticker}|{day}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
    path.write_text(f"{text}\n", encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def child_environment(action: str) -> dict[str, str]:
    """Give vendor keys only to the step that contacts a vendor."""
    environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    if action == "fetch":
        return environment
    return {
        name: value
        for name, value in environment.items()
        if name not in VENDOR_KEYS and not name.startswith(VENDOR_KEY_PREFIXES)
    }


def run_provider(
    provider: Provider,
    action: str,
    request: dict[str, Any],
    output: Path,
    provider_commands: Mapping[str, Sequence[str]] | None,
) -> None:
    server = REPO_ROOT / "mcp-servers" / provider.server
    command = list((provider_commands or {}).get(provider.name, ()))
    if not command:
        command = [shutil.which("uv") or "uv", "run"]
        if provider.env_file:
            command += ["--env-file", str(server / ".env")]
        command.append(str(server / "capture.py"))
    with tempfile.TemporaryDirectory() as folder:
        request_path = Path(folder) / "request.json"
        write_json(request_path, request)
        subprocess.run(
            [*command, action, "--request", str(request_path), "--output", str(output)],
            check=True,
            cwd=REPO_ROOT,
            env=child_environment(action),
        )


def raw_dir(root: Path, provider: Provider, ticker: str) -> Path:
    return root / provider.sources[0] / short_key(ticker)


def provider_request(
    root: Path,
    provider: Provider,
    ticker: str,
    meta: Mapping[str, Any],
    candidates: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "start": meta["start"],
        "end": meta["end"],
        "candidates": list(candidates),
        "raw": str(raw_dir(root, provider, ticker)),
    }


def normalized_records(
    root: Path,
    provider: Provider,
    ticker: str,
    meta: Mapping[str, Any],
    candidates: Sequence[Mapping[str, str]],
    provider_commands: Mapping[str, Sequence[str]] | None,
) -> tuple[list[Record], dict[str, dict[str, Any]]]:
    """Return a provider's records, first per id, and its coverage by date."""
    request = provider_request(root, provider, ticker, meta, candidates)
    with tempfile.TemporaryDirectory() as folder:
        run_provider(provider, "normalize", request, Path(folder), provider_commands)
        lines = (Path(folder) / "records.jsonl").read_text(encoding="utf-8")
        coverage_path = Path(folder) / "coverage.json"
        coverage = read_json(coverage_path) if coverage_path.exists() else {}
    records = {}
    for line in lines.splitlines():
        record = record_from_dict(json.loads(line))
        records.setdefault((record.source, record.id), record)
    return list(records.values()), coverage


def closed_sessions(records: Sequence[Record], started_at: datetime) -> list[date]:
    """Keep sessions whose market close came before capture began."""
    sessions = []
    for record in records:
        day = date.fromisoformat(record.id)
        closing = datetime.combine(day, MARKET_CLOSE, NEW_YORK)
        if closing <= started_at:
            sessions.append(day)
    return sessions


def last_closed_friday(started_at: datetime) -> date:
    """Return the latest scheduled Friday whose market close has passed."""
    now = started_at.astimezone(NEW_YORK)
    friday = now.date() - timedelta(days=(now.weekday() - FRIDAY) % 7)
    if friday == now.date() and now.time() < MARKET_CLOSE:
        friday -= timedelta(days=7)
    return friday


def candidate_dates(
    start: date, end: date, min_date: date, sessions: Sequence[date]
) -> list[dict[str, str]]:
    dates = [day for day in study_dates(start, end, sessions) if day >= min_date]
    return [
        {
            "date": day.isoformat(),
            "cutoff": format_instant(cutoff_for(day, sessions)),
            "execution": day.isoformat(),
            "exit": following.isoformat(),
        }
        for day, following in zip(dates, dates[1:])
    ]


def capture(
    capture_id: str,
    start: date,
    end: date,
    min_date: date,
    *,
    tickers: Sequence[str] = TICKERS,
    captures_root: Path = DATA_ROOT / "captures",
    provider_commands: Mapping[str, Sequence[str]] | None = None,
) -> Path:
    """Fetch every source once; a repeated call resumes unfinished slices."""
    root = captures_root / identifier(capture_id)
    meta_path = root / "capture.json"
    scope = {
        "capture_id": capture_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "min_date": min_date.isoformat(),
        "tickers": list(tickers),
    }
    if not meta_path.exists():
        started = format_instant(datetime.now(timezone.utc))
        write_json(meta_path, {**scope, "started_at": started})
    meta = read_json(meta_path)
    if {name: meta[name] for name in scope} != scope:
        raise ValueError(f"Capture {capture_id} was started with different arguments")
    for ticker in meta["tickers"]:
        request = provider_request(root, MARKET, ticker, meta, [])
        run_provider(
            MARKET,
            "fetch",
            request,
            raw_dir(root, MARKET, ticker),
            provider_commands,
        )
    candidates_path = root / "candidates.json"
    if not candidates_path.exists():
        started_at = parse_instant(meta["started_at"])
        sessions: set[date] = set()
        for ticker in meta["tickers"]:
            records, _ = normalized_records(
                root, MARKET, ticker, meta, [], provider_commands
            )
            sessions.update(closed_sessions(records, started_at))
        write_json(
            candidates_path,
            candidate_dates(
                start,
                min(end, last_closed_friday(started_at)),
                min_date,
                sorted(sessions),
            ),
        )
    candidates = read_json(candidates_path)
    for provider in CAPTURE_PROVIDERS:
        if provider == MARKET:
            continue
        for ticker in meta["tickers"]:
            request = provider_request(root, provider, ticker, meta, candidates)
            output = raw_dir(root, provider, ticker)
            run_provider(provider, "fetch", request, output, provider_commands)
    return root


def capture_hash(root: Path) -> str:
    lines = sorted(
        f"{path.relative_to(root).as_posix()}:{hash_file(path)}"
        for provider in CAPTURE_PROVIDERS
        for path in (root / provider.sources[0]).rglob("*.json")
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def price_coverage(
    records: Sequence[Record], candidate: Mapping[str, str]
) -> dict[str, Any]:
    days = {record.id for record in records}
    prior = last_admitted_date(parse_instant(candidate["cutoff"])).isoformat()
    required = {prior, candidate["execution"], candidate["exit"]}
    admitted = [
        record.id
        for record in records
        if admit(record.public_at, parse_instant(candidate["cutoff"]))
    ]
    return {
        "reachable": bool(records),
        "records": len(admitted),
        "truncated": False,
        "earliest_reached": min(admitted, default=None),
        "latest_reached": max(admitted, default=None),
        "required_start": prior,
        "coverage_rule_met": required <= days,
        "dropped_rows": 0,
    }


def longest_run(
    candidates: Sequence[Mapping[str, str]], complete: set[str]
) -> list[Mapping[str, str]]:
    best: list[Mapping[str, str]] = []
    current: list[Mapping[str, str]] = []
    for candidate in candidates:
        current = [*current, candidate] if candidate["date"] in complete else []
        if len(current) > len(best):
            best = current
    return best


def admitted_records(
    records: Sequence[Record], cutoff: datetime, source: str
) -> list[dict[str, Any]]:
    lookback = LOOKBACK_DAYS[source]
    kept = [record for record in records if admit(record.public_at, cutoff)]
    if lookback is not None:
        kept = [
            record
            for record in kept
            if (cutoff - record.public_at).total_seconds() <= lookback * 86400
        ]
    return [record_to_dict(record) for record in kept]


def build(
    capture_id: str,
    dataset_id: str,
    *,
    captures_root: Path = DATA_ROOT / "captures",
    datasets_root: Path = DATA_ROOT / "datasets",
    scoring_root: Path = DATA_ROOT / "scoring",
    provider_commands: Mapping[str, Sequence[str]] | None = None,
) -> str:
    """Write one frozen dataset offline and return its manifest hash."""
    root = captures_root / identifier(capture_id)
    dataset = datasets_root / identifier(dataset_id)
    if dataset.exists():
        raise FileExistsError(f"Dataset {dataset_id} already exists")
    if (root / PURGED_MARKER).exists():
        raise ValueError(f"Capture {capture_id} was purged")
    meta = read_json(root / "capture.json")
    candidates = read_json(root / "candidates.json")
    tickers = meta["tickers"]
    sources = [source for item in CAPTURE_PROVIDERS for source in item.sources]
    records: dict[tuple[str, str], list[Record]] = {}
    coverage: dict[tuple[str, str], dict[str, Any]] = {}
    for ticker in tickers:
        for provider in CAPTURE_PROVIDERS:
            items, entries = normalized_records(
                root, provider, ticker, meta, candidates, provider_commands
            )
            for source in provider.sources:
                records[ticker, source] = [i for i in items if i.source == source]
            for candidate in candidates:
                found = entries.get(candidate["date"], {})
                coverage.setdefault((ticker, candidate["date"]), {}).update(
                    {
                        source: found.get(source, UNREACHABLE)
                        for source in provider.sources
                        if provider != MARKET
                    }
                )
        for candidate in candidates:
            coverage[ticker, candidate["date"]]["prices"] = price_coverage(
                records[ticker, "prices"], candidate
            )
    complete = {
        candidate["date"]
        for candidate in candidates
        if all(
            entry["coverage_rule_met"]
            for ticker in tickers
            for entry in coverage[ticker, candidate["date"]].values()
        )
    }
    calendar = longest_run(candidates, complete)
    if not calendar:
        raise ValueError("No study date meets every coverage rule")

    datasets_root.mkdir(parents=True, exist_ok=True)
    building = Path(tempfile.mkdtemp(prefix=f"{dataset_id}.", dir=datasets_root))
    copies: dict[str, Any] = {}
    scoring = []
    for candidate in calendar:
        day = candidate["date"]
        cutoff = parse_instant(candidate["cutoff"])
        for ticker in tickers:
            key = copy_key(ticker, day)
            folder = building / "copies" / key
            for source in sources:
                items = admitted_records(records[ticker, source], cutoff, source)
                write_json(
                    folder / f"{source}.json", {"source": source, "records": items}
                )
            write_json(folder / "coverage.json", coverage[ticker, day])
            copies[f"{ticker}|{day}"] = {
                "key": key,
                "files": {
                    path.name: hash_file(path) for path in sorted(folder.iterdir())
                },
            }
            closes = {
                item.id: item.payload["Close"] for item in records[ticker, "prices"]
            }
            scoring.append(
                {
                    "ticker": ticker,
                    "date": day,
                    "execution_date": candidate["execution"],
                    "execution_close": closes[candidate["execution"]],
                    "exit_date": candidate["exit"],
                    "exit_close": closes[candidate["exit"]],
                }
            )
    scoring_file = scoring_root / dataset_id / "scoring.json"
    write_json(scoring_file, scoring)
    included = {item["date"] for item in calendar}
    total_bytes = scoring_file.stat().st_size + sum(
        path.stat().st_size for path in building.rglob("*") if path.is_file()
    )
    manifest_path = building / "manifest.json"
    write_json(
        manifest_path,
        {
            "version": 1,
            "dataset_id": dataset_id,
            "capture_id": capture_id,
            "capture_hash": capture_hash(root),
            "min_date": meta["min_date"],
            "tickers": {ticker: short_key(ticker) for ticker in tickers},
            "dates": list(calendar),
            "copies": copies,
            "scoring": {"scoring.json": hash_file(scoring_file)},
            "coverage_summary": {
                "excluded_dates": [
                    item["date"] for item in candidates if item["date"] not in included
                ]
            },
            "total_bytes": total_bytes,
            "built_at": format_instant(datetime.now(timezone.utc)),
        },
    )
    digest = hash_file(manifest_path)
    os.replace(building, dataset)
    print(f"Dataset {dataset_id}: hash {digest}; total bytes {total_bytes}")
    print(f"Study dates: {calendar[0]['date']} to {calendar[-1]['date']}")
    return str(digest)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture_parser = commands.add_parser("capture")
    capture_parser.add_argument("--capture-id", required=True)
    capture_parser.add_argument("--start", type=date.fromisoformat, required=True)
    capture_parser.add_argument("--end", type=date.fromisoformat, required=True)
    capture_parser.add_argument("--min-date", type=date.fromisoformat, required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--capture-id", required=True)
    build_parser.add_argument("--dataset-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            capture(args.capture_id, args.start, args.end, args.min_date)
        else:
            build(args.capture_id, args.dataset_id)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"{args.command} failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
