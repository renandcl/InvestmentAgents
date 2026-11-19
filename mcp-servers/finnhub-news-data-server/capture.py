# ruff: noqa: E402
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.providers.capture import run_cli
from services.finnhub_news_service import coverage, fetch, normalize

if __name__ == "__main__":
    raise SystemExit(run_cli(fetch, normalize, coverage=coverage))
