from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal

import yfinance as yf

from runtime.providers.cache import configure_yfinance, service_cache
from runtime.providers.capture import read_slice, slice_finished, write_slice
from runtime.providers.timecut import Record, public_at_from_date

if TYPE_CHECKING:
    from runtime.providers.cache import RunCache

HISTORY_SLICE = "history"
PRICE_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


def fetch(request: dict[str, Any], output: Path) -> None:
    """Store the full unrounded adjusted daily history once."""
    if slice_finished(output, HISTORY_SLICE):
        return
    cache = output / ".yfinance"
    cache.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache))
    history = yf.Ticker(request["ticker"]).history(period="max", auto_adjust=True)
    bars = [
        {"Date": index.date().isoformat(), **{c: float(row[c]) for c in PRICE_COLUMNS}}
        for index, row in history.iterrows()
    ]
    write_slice(output, HISTORY_SLICE, bars)


def normalize(request: dict[str, Any], raw: Path) -> list[Record]:
    records = []
    for bar in read_slice(raw, HISTORY_SLICE):
        payload = {column: bar[column] for column in PRICE_COLUMNS}
        public_at = public_at_from_date(date.fromisoformat(bar["Date"]))
        records.append(Record(bar["Date"], public_at, "prices", payload))
    return records


class YFinMarketDataService:
    def __init__(self, *, cache: RunCache | None = None) -> None:
        self.cache = service_cache("yfin-market-data-server", cache)
        configure_yfinance(self.cache, yfinance=yf)

    def get_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: bool = True,
        output_format: Literal["markdown", "csv"] = "markdown",
    ) -> str:
        """Fetch OHLCV data using the run-owned provider cache."""
        # validate dates (raises ValueError if malformed)
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")

        sym_up = symbol.upper()
        key = self.cache.key(
            "ohlcv",
            {"symbol": sym_up, "start": start_date, "end": end_date, "adjust": adjust},
        )
        cached = self.cache.read_json(key)
        records: List[Dict] = cached["data"] if cached else []

        if not records:
            ticker = yf.Ticker(sym_up)
            df = ticker.history(start=start_date, end=end_date, auto_adjust=adjust)
            if df.empty:
                return (
                    f"No data found for {sym_up} between {start_date} and {end_date}."
                )
            # Ensure consistent column set
            cols = [
                c
                for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
                if c in df.columns
            ]
            df = df[cols]
            # Round numeric prices (not volume)
            for price_col in [c for c in cols if c not in ("Volume",)]:
                df[price_col] = df[price_col].round(2)
            # Persist records (Date as ISO date string)
            tmp = df.reset_index()
            tmp["Date"] = tmp["Date"].astype(str)
            records = [
                {"Date": row["Date"][:10], **{c: row[c] for c in cols}}
                for _, row in tmp.iterrows()
            ]
            payload = {
                "symbol": sym_up,
                "start_date": start_date,
                "end_date": end_date,
                "adjust": adjust,
                "retrieved": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "columns": cols,
                "data": records,
            }
            self.cache.write_json(key, payload)
        else:
            # columns infer from first record ordering (preserve typical order)
            exemplar = records[0]
            # Known preferred order
            preferred = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
            cols = [c for c in preferred if c in exemplar]

        if not records:
            return f"No data found for {sym_up} between {start_date} and {end_date}."

        if output_format == "csv":
            header_meta = (
                f"# YFinance data for {sym_up} from {start_date} to {end_date}\n"
                f"# Records: {len(records)}\n"
            )
            # CSV header
            csv_cols = ["Date"] + cols
            lines = [",".join(csv_cols)]
            for r in records:
                line = ",".join(str(r.get(c, "")) for c in csv_cols)
                lines.append(line)
            return header_meta + "\n".join(lines)

        # markdown output
        table_header = (
            "| Date | "
            + " | ".join([c.replace("Adj Close", "Adj_Close") for c in cols])
            + " |\n"
        )
        table_sep = "|" + " --- |" * (len(cols) + 1) + "\n"
        rows = "".join(
            f"| {r['Date']} | " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n"
            for r in records
        )
        return (
            f"## YFinance OHLCV for {sym_up} from {start_date} to {end_date}\n\n"
            + table_header
            + table_sep
            + rows
        )


if __name__ == "__main__":
    svc = YFinMarketDataService()
    print(svc.get_data("AAPL", "2025-08-01", "2025-08-05"))
