"""Remove stored Reddit content once research is complete.

Reddit's Data API terms require deleted content to be removed from stored copies,
so this purges every verbatim copy the system keeps:

- run provider caches: ``data/runs/<run_id>/cache/reddit-news-data-server/``
- ``get_reddit_news`` and ``get_reddit_sentiment`` tool results in run session transcripts, replaced with a
  redaction marker so the conversations stay readable

Finished runs are eligible by default. Use --abandoned-run RUN_ID only after
confirming that its owner and children have stopped; this allows cleanup after
a hard kill without changing run status. Legacy data is never read or modified. Reports, run state
and memories hold LLM-written summaries, not Reddit posts, and are left alone so
committed artifact hashes stay valid.

Dry run by default; pass ``--apply`` to delete:

    uv run python -B -m utils.purge_reddit [--abandoned-run RUN_ID] [--apply]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Iterable, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runtime.context import REPO_ROOT
from runtime.store import TERMINAL

REDDIT_PROVIDER = "reddit-news-data-server"
REDDIT_TOOLS = frozenset({"get_reddit_news", "get_reddit_sentiment"})
REDACTED = "[Reddit content removed after research completed]"


@dataclass
class PurgeReport:
    cache_dirs: list[Path] = field(default_factory=list)
    redacted_messages: list[Path] = field(default_factory=list)
    skipped_runs: list[tuple[Path, str | None]] = field(default_factory=list)


def run_status(run_root: Path) -> str | None:
    database = run_root / "run.sqlite3"
    if not database.is_file():
        return None
    try:
        with closing(
            sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
        ) as db:
            return db.execute("SELECT status FROM run").fetchone()[0]
    except sqlite3.Error:
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def redact_sessions(sessions_root: Path, report: PurgeReport, *, apply: bool) -> None:
    """Redact Reddit tool results in Strands FileSessionManager transcripts."""
    for messages_dir in sorted(sessions_root.rglob("messages")):
        if not messages_dir.is_dir():
            continue
        files = sorted(messages_dir.glob("message_*.json"))
        loaded = []
        reddit_ids = set()
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            loaded.append((path, data))
            for block in (data.get("message") or {}).get("content") or []:
                tool_use = block.get("toolUse") if isinstance(block, dict) else None
                if tool_use and tool_use.get("name") in REDDIT_TOOLS:
                    reddit_ids.add(tool_use.get("toolUseId"))
        if not reddit_ids:
            continue
        for path, data in loaded:
            changed = False
            for block in (data.get("message") or {}).get("content") or []:
                result = block.get("toolResult") if isinstance(block, dict) else None
                if (
                    result
                    and result.get("toolUseId") in reddit_ids
                    and result.get("content") != [{"text": REDACTED}]
                ):
                    result["content"] = [{"text": REDACTED}]
                    changed = True
            if changed:
                report.redacted_messages.append(path)
                if apply:
                    _write_json(path, data)


def purge(
    runs_root: Path, *, abandoned_runs: Iterable[str] = (), apply: bool = False
) -> PurgeReport:
    report = PurgeReport()
    abandoned = frozenset(abandoned_runs)
    root = runs_root.resolve()
    if runs_root.is_dir():
        for run_root in sorted(p for p in runs_root.iterdir() if p.is_dir()):
            status = run_status(run_root)
            if not run_root.resolve().is_relative_to(root) or (
                status not in TERMINAL and run_root.name not in abandoned
            ):
                report.skipped_runs.append((run_root, status))
                continue
            cache = run_root / "cache" / REDDIT_PROVIDER
            if cache.is_dir():
                report.cache_dirs.append(cache)
                if not cache.resolve().is_relative_to(run_root.resolve()):
                    raise ValueError("Reddit cache escapes its run directory")
                if apply:
                    shutil.rmtree(cache)
            sessions = run_root / "sessions"
            if sessions.is_dir():
                if not sessions.resolve().is_relative_to(run_root.resolve()):
                    raise ValueError("Session directory escapes its run")
                redact_sessions(sessions, report, apply=apply)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path, default=REPO_ROOT / "data" / "runs")
    parser.add_argument(
        "--abandoned-run",
        action="append",
        default=[],
        metavar="RUN_ID",
        help="purge a named nonterminal run confirmed stopped, including its owned children",
    )
    parser.add_argument(
        "--apply", action="store_true", help="delete; without it, only list"
    )
    args = parser.parse_args(argv)
    report = purge(
        args.runs_root,
        abandoned_runs=args.abandoned_run,
        apply=args.apply,
    )
    verb = "Removed" if args.apply else "Would remove"
    for path in report.cache_dirs:
        print(f"{verb} cache directory {path}")
    for path in report.redacted_messages:
        print(f"{'Redacted' if args.apply else 'Would redact'} {path}")
    for path, status in report.skipped_runs:
        print(f"Skipped unfinished run {path} (status {status})", file=sys.stderr)
    print(
        f"{verb} {len(report.cache_dirs)} run caches; "
        f"{'redacted' if args.apply else 'would redact'} "
        f"{len(report.redacted_messages)} session messages; "
        f"skipped {len(report.skipped_runs)} unfinished runs."
    )
    if not args.apply:
        print("Dry run only. Re-run with --apply to delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
