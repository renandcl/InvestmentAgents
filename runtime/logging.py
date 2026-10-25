"""Shared logging policy for batch and standalone application entry points."""

from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    level = os.environ.get("INVESTMENT_LOG_LEVEL", "INFO").strip().upper()
    logging.basicConfig(
        level=level,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger().setLevel(level)
    logging.getLogger("strands").setLevel(level)
