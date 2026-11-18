"""Child-process protocol shared by each provider's `capture.py` (spec 006)."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from runtime.providers.timecut import Record, format_instant, parse_instant

Fetch = Callable[[dict[str, Any], Path], None]
Normalize = Callable[[dict[str, Any], Path], list[Record]]


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
    fetch: Fetch, normalize: Normalize, argv: Sequence[str] | None = None
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
    return 0
