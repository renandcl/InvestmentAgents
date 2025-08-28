import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import yfinance as yf
from stockstats import wrap

from .stockstats_utils import StockstatsUtils


class StockstatsService:
    def __init__(self, cache_dir: str = "data/market_data/price_data"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_stock_stats_indicators_window(
        self,
        symbol: str,
        indicator: str,
        curr_date: str,
        look_back_days: int,
    ) -> str:
        """Return rolling window of indicator values plus description."""

        # Download window of data (always online for now)
        end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=look_back_days)
        data = yf.download(symbol, start=start_dt, end=end_dt, progress=False)
        data = wrap(data)

        best_ind_params = {
            "close_50_sma": "50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.",
            "close_200_sma": "200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.",
            "close_10_ema": "10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.",
            "macd": "MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.",
            "macds": "MACD Signal: EMA smoothing of the MACD line. Usage: Crossovers with MACD line to trigger trades. Tips: Use within broader strategy.",
            "macdh": "MACD Histogram: Gap between MACD line and signal; visualize momentum strength, spot divergence early.",
            "rsi": "RSI: Momentum overbought/oversold (70/30). Divergences can flag reversals; can stay extreme in strong trends.",
            "boll": "Bollinger Middle (20 SMA) base for bands; dynamic benchmark for price movement.",
            "boll_ub": "Bollinger Upper Band (2σ above middle). Potential overbought / breakout zone; price can ride band in trends.",
            "boll_lb": "Bollinger Lower Band (2σ below middle). Potential oversold / reversal zone; confirm with other signals.",
            "atr": "ATR: Average True Range volatility measure. Use for stop placement / position sizing.",
            "vwma": "VWMA: Volume-weighted moving average; confirms trends integrating price + volume.",
            "mfi": "MFI: Money Flow Index (price * volume). Overbought >80 / oversold <20; divergences flag potential reversals.",
        }

        if indicator not in best_ind_params:
            raise ValueError(
                f"Indicator {indicator} is not supported. Choose from: {', '.join(best_ind_params.keys())}"
            )

        # Iterate backwards day by day (calendar days; weekend/holiday handled in util)
        values_block = []
        iter_dt = end_dt
        earliest = end_dt - relativedelta(days=look_back_days)
        while iter_dt >= earliest:
            val = self._get_stockstats_indicator(
                symbol, indicator, iter_dt.strftime("%Y-%m-%d"), curr_date
            )
            values_block.append(f"{iter_dt.strftime('%Y-%m-%d')}: {val}")
            iter_dt -= relativedelta(days=1)

        values_block.reverse()  # chronological ascending
        values_text = "\n".join(values_block)
        description = best_ind_params[indicator]
        return (
            f"## {indicator} values from {earliest.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            f"{values_text}\n\n{description}"
        )

    def _get_stockstats_indicator(
        self, symbol: str, indicator: str, curr_date: str, end_date: str
    ) -> str:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        curr_str = curr_dt.strftime("%Y-%m-%d")
        try:
            indicator_value = StockstatsUtils.get_stock_stats(
                symbol, indicator, curr_str, end_date
            )
        except Exception as e:  # noqa: BLE001
            print(
                f"Error getting stockstats indicator {indicator} for {curr_str}: {e}"
            )
            return ""
        return str(indicator_value)


if __name__ == "__main__":
    svc = StockstatsService()
    print(
        svc.get_stock_stats_indicators_window(
            "AAPL", "close_50_sma", datetime.now().strftime("%Y-%m-%d"), 5
        )
    )
