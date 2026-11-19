"""Child-process protocol shared by each provider's `capture.py` (spec 006)."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from runtime.providers.timecut import (
    NEW_YORK,
    Record,
    format_instant,
    last_admitted_date,
    parse_instant,
)

Fetch = Callable[[dict[str, Any], Path], None]
Normalize = Callable[[dict[str, Any], Path], list[Record]]
Coverage = Callable[[dict[str, Any], Path], dict[str, dict[str, Any]]]
WindowRequest = Callable[[date, date], list[dict[str, Any]]]
WINDOW_DAYS = 30


def slice_finished(output: Path, name: str) -> bool:
    return (output / f"{name}.done").exists()


def write_slice(output: Path, name: str, data: Any) -> None:
    """Write one raw response; a finished slice is never rewritten."""
    if slice_finished(output, name):
        return
    output.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    (output / f"{name}.json").write_text(text, encoding="utf-8")
    (output / f"{name}.done").touch()


def read_slice(raw: Path, name: str) -> Any:
    return json.loads((raw / f"{name}.json").read_text(encoding="utf-8"))


def fetch_windows(
    output: Path,
    name: str,
    start: date,
    end: date,
    request: WindowRequest,
    page_max: int | None,
) -> None:
    """Fetch 30-day windows, halving a saturated one down to a single day."""
    pending = []
    day = start
    while day <= end:
        last = min(day + timedelta(days=WINDOW_DAYS - 1), end)
        pending.append((day, last))
        day = last + timedelta(days=1)
    while pending:
        first, last = pending.pop(0)
        slice_name = f"{name}-{first.isoformat()}-{last.isoformat()}"
        if slice_finished(output, slice_name):
            continue
        rows = request(first, last)
        saturated = page_max is not None and len(rows) >= page_max
        if saturated and first < last:
            middle = first + (last - first) // 2
            pending[:0] = [(first, middle), (middle + timedelta(days=1), last)]
            continue
        window = {"start": first.isoformat(), "end": last.isoformat()}
        write_slice(
            output, slice_name, {**window, "saturated": saturated, "rows": rows}
        )


def read_windows(raw: Path, name: str) -> list[dict[str, Any]]:
    paths = sorted(raw.glob(f"{name}-*.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def window_coverage(
    records: Sequence[Record],
    windows: Sequence[dict[str, Any]],
    candidate: dict[str, str],
    lookback_days: int,
    page_max: int | None,
    dropped_rows: int,
    filing_lag_days: int = 0,
) -> dict[str, Any]:
    """Reach the lookback start with no saturated page.

    Windows keyed by trade date can hold filings up to `filing_lag_days` later,
    so their saturation counts that far before the lookback start.
    """
    cutoff = parse_instant(candidate["cutoff"])
    required = (cutoff.astimezone(NEW_YORK) - timedelta(days=lookback_days)).date()
    earliest = required - timedelta(days=filing_lag_days)
    last = last_admitted_date(cutoff)
    starts = [date.fromisoformat(window["start"]) for window in windows]
    ends = [date.fromisoformat(window["end"]) for window in windows]
    truncated = any(
        window["saturated"]
        for window in windows
        if window["start"] <= last.isoformat() and window["end"] >= earliest.isoformat()
    )
    admitted = [
        record
        for record in records
        if record.public_at <= cutoff
        and (cutoff - record.public_at) <= timedelta(days=lookback_days)
    ]
    reached = bool(windows) and min(starts) <= required and max(ends) >= last
    return {
        "reachable": bool(windows),
        "records": len(admitted),
        "truncated": truncated,
        "earliest_reached": min(starts).isoformat() if starts else None,
        "latest_reached": max(ends).isoformat() if ends else None,
        "required_start": required.isoformat(),
        "coverage_rule_met": reached and not truncated,
        "page_max_unverified": page_max is None,
        "dropped_rows": dropped_rows,
    }


def record_to_dict(record: Record) -> dict[str, Any]:
    return {
        "id": record.id,
        "public_at": format_instant(record.public_at),
        "source": record.source,
        "payload": record.payload,
    }


def record_from_dict(data: dict[str, Any]) -> Record:
    return Record(
        data["id"], parse_instant(data["public_at"]), data["source"], data["payload"]
    )


def run_cli(
    fetch: Fetch,
    normalize: Normalize,
    argv: Sequence[str] | None = None,
    coverage: Coverage | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("fetch", "normalize"))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    if args.action == "fetch":
        fetch(request, args.output)
        return 0
    records = normalize(request, Path(request["raw"]))
    lines = [
        json.dumps(record_to_dict(record), ensure_ascii=False) for record in records
    ]
    (args.output / "records.jsonl").write_text(
        "".join(f"{line}\n" for line in lines), encoding="utf-8"
    )
    if coverage is not None:
        entries = coverage(request, Path(request["raw"]))
        (args.output / "coverage.json").write_text(
            json.dumps(entries, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
    return 0
