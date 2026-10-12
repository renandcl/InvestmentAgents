"""All standalone agent and memory examples allocate a fresh managed run."""

import argparse
import asyncio
from pathlib import Path

from runtime.context import MemoryMode, RunConfig
from runtime.lifecycle import create_run
from runtime.logging import configure_logging


def run_example(agent_factory, required_report_key):
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--date", default="2025-08-01")
    parser.add_argument(
        "--memory-mode", choices=list(MemoryMode), default=MemoryMode.OFF
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--memory-request-timeout", type=float, default=600.0)
    parser.add_argument("--message", default="Provide the analysis.")
    args = parser.parse_args()
    configure_logging()
    options = {"output_root": args.output_root} if args.output_root else {}
    runtime = create_run(
        RunConfig(
            args.ticker,
            args.date,
            memory_mode=args.memory_mode,
            memory_request_timeout=args.memory_request_timeout,
            **options,
        )
    )
    result = asyncio.run(
        runtime.execute(agent_factory, args.message, required_report_key)
    )
    print(f"Run {result.run_id}: {result.status}; report: {result.report_path}")
    return result
