"""Remove stored Reddit content once research is complete.

Reddit's Data API terms require deleted content to be removed from stored copies,
so this purges every verbatim copy the system keeps:

- run provider caches: ``data/runs/<run_id>/cache/reddit-news-data-server/``
- ``get_reddit_news`` and ``get_reddit_sentiment`` tool results in run session transcripts, replaced with a
  redaction marker so the conversations stay readable
- with ``--include-legacy``: ``data/news_data/reddit_news_*.json`` and the
  transcripts under ``data/agents_sessions/``

Only finished runs (SUCCEEDED/FAILED/CANCELLED) are touched. Reports, run state
and memories hold LLM-written summaries, not Reddit posts, and are left alone so
committed artifact hashes stay valid.

Dry run by default; pass ``--apply`` to delete:

    uv run python -B -m utils.purge_reddit [--include-legacy] [--apply]
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from runtime.context import REPO_ROOT
from runtime.store import TERMINAL

REDDIT_PROVIDER = "reddit-news-data-server"
REDDIT_TOOLS = frozenset({"get_reddit_news", "get_reddit_sentiment"})
REDACTED = "[Reddit content removed after research completed]"


@dataclass
class PurgeReport:
    cache_dirs: list = field(default_factory=list)
    cache_files: list = field(default_factory=list)
    redacted_messages: list = field(default_factory=list)
    skipped_runs: list = field(default_factory=list)


def run_status(run_root):
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


def _write_json(path, data):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def redact_sessions(sessions_root, report, *, apply):
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


def purge(runs_root, *, legacy_root=None, apply=False):
    report = PurgeReport()
    if runs_root.is_dir():
        for run_root in sorted(p for p in runs_root.iterdir() if p.is_dir()):
            status = run_status(run_root)
            if status not in TERMINAL:
                report.skipped_runs.append((run_root, status))
                continue
            cache = run_root / "cache" / REDDIT_PROVIDER
            if cache.is_dir():
                report.cache_dirs.append(cache)
                if apply:
                    shutil.rmtree(cache)
            sessions = run_root / "sessions"
            if sessions.is_dir():
                redact_sessions(sessions, report, apply=apply)
    if legacy_root is not None:
        news = legacy_root / "news_data"
        if news.is_dir():
            for path in sorted(news.glob("reddit_news_*.json")):
                report.cache_files.append(path)
                if apply:
                    path.unlink()
        sessions = legacy_root / "agents_sessions"
        if sessions.is_dir():
            redact_sessions(sessions, report, apply=apply)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", type=Path, default=REPO_ROOT / "data" / "runs")
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="also purge pre-isolation data under data/ (news_data, agents_sessions)",
    )
    parser.add_argument("--legacy-root", type=Path, default=REPO_ROOT / "data")
    parser.add_argument(
        "--apply", action="store_true", help="delete; without it, only list"
    )
    args = parser.parse_args(argv)
    report = purge(
        args.runs_root,
        legacy_root=args.legacy_root if args.include_legacy else None,
        apply=args.apply,
    )
    verb = "Removed" if args.apply else "Would remove"
    for path in report.cache_dirs:
        print(f"{verb} cache directory {path}")
    for path in report.cache_files:
        print(f"{verb} cache file {path}")
    for path in report.redacted_messages:
        print(f"{'Redacted' if args.apply else 'Would redact'} {path}")
    for path, status in report.skipped_runs:
        print(f"Skipped unfinished run {path} (status {status})", file=sys.stderr)
    print(
        f"{verb} {len(report.cache_dirs)} run caches and "
        f"{len(report.cache_files)} legacy cache files; "
        f"{'redacted' if args.apply else 'would redact'} "
        f"{len(report.redacted_messages)} session messages; "
        f"skipped {len(report.skipped_runs)} unfinished runs."
    )
    if not args.apply:
        print("Dry run only. Re-run with --apply to delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
