import os
from datetime import datetime, timedelta
from stockstats import wrap
import yfinance as yf
from stockstats_utils import StockstatsUtils
from dateutil.relativedelta import relativedelta

class StockstatsService:
    def __init__(self, cache_dir: str = "data/market_data/price_data"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_stock_stats_indicators_window(
        self,
        symbol,
        indicator,
        curr_date,
        look_back_days,
        online,
    ) -> str:
        """
        Get the stock stats indicators window for a specific symbol and indicator.

        Args:
            symbol (str): The ticker symbol of the company.
            indicator (str): The technical indicator to get the analysis and report of.
            curr_date (str): The current trading date you are trading on, in YYYY-mm-dd format.
            look_back_days (int): The number of days to look back.
            online (bool): Whether to fetch data online or offline.

        Returns:
            str: The stock stats indicators window for the specified symbol and indicator.
        """
        if online:
            # Fetch data online
            end_date = datetime.strptime(curr_date, "%Y-%m-%d")
            start_date = end_date - timedelta(days=look_back_days)
            data = yf.download(symbol, start=start_date, end=end_date)
            data = wrap(data)

        best_ind_params = {
            # Moving Averages
            "close_50_sma": (
                "50 SMA: A medium-term trend indicator. "
                "Usage: Identify trend direction and serve as dynamic support/resistance. "
                "Tips: It lags price; combine with faster indicators for timely signals."
            ),
            "close_200_sma": (
                "200 SMA: A long-term trend benchmark. "
                "Usage: Confirm overall market trend and identify golden/death cross setups. "
                "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
            ),
            "close_10_ema": (
                "10 EMA: A responsive short-term average. "
                "Usage: Capture quick shifts in momentum and potential entry points. "
                "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
            ),
            # MACD Related
            "macd": (
                "MACD: Computes momentum via differences of EMAs. "
                "Usage: Look for crossovers and divergence as signals of trend changes. "
                "Tips: Confirm with other indicators in low-volatility or sideways markets."
            ),
            "macds": (
                "MACD Signal: An EMA smoothing of the MACD line. "
                "Usage: Use crossovers with the MACD line to trigger trades. "
                "Tips: Should be part of a broader strategy to avoid false positives."
            ),
            "macdh": (
                "MACD Histogram: Shows the gap between the MACD line and its signal. "
                "Usage: Visualize momentum strength and spot divergence early. "
                "Tips: Can be volatile; complement with additional filters in fast-moving markets."
            ),
            # Momentum Indicators
            "rsi": (
                "RSI: Measures momentum to flag overbought/oversold conditions. "
                "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
                "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
            ),
            # Volatility Indicators
            "boll": (
                "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
                "Usage: Acts as a dynamic benchmark for price movement. "
                "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
            ),
            "boll_ub": (
                "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
                "Usage: Signals potential overbought conditions and breakout zones. "
                "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
            ),
            "boll_lb": (
                "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
                "Usage: Indicates potential oversold conditions. "
                "Tips: Use additional analysis to avoid false reversal signals."
            ),
            "atr": (
                "ATR: Averages true range to measure volatility. "
                "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
                "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
            ),
            # Volume-Based Indicators
            "vwma": (
                "VWMA: A moving average weighted by volume. "
                "Usage: Confirm trends by integrating price action with volume data. "
                "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
            ),
            "mfi": (
                "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
                "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
                "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
            ),
        }

        if indicator not in best_ind_params:
            raise ValueError(
                f"Indicator {indicator} is not supported. Please choose from: {list(best_ind_params.keys())}"
            )

        end_date = curr_date
        curr_date = datetime.strptime(curr_date, "%Y-%m-%d")
        before = curr_date - relativedelta(days=look_back_days)

        # online gathering
        ind_string = ""
        while curr_date >= before:
            indicator_value = self._get_stockstats_indicator(
                symbol, indicator, curr_date.strftime("%Y-%m-%d"), end_date
            )

            ind_string += f"{curr_date.strftime('%Y-%m-%d')}: {indicator_value}\n"

            curr_date = curr_date - relativedelta(days=1)

        result_str = (
            f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date}:\n\n"
            + ind_string
            + "\n\n"
            + best_ind_params.get(indicator, "No description available.")
        )

        return result_str


    def _get_stockstats_indicator(self, symbol, indicator, curr_date, end_date) -> str:
        """ Get the stock stats indicator for a specific symbol and indicator.

        Args:
            symbol (str): The ticker symbol of the company.
            indicator (str): The technical indicator to get the analysis and report of.
            curr_date (str): The current trading date you are trading on, in YYYY-mm-dd format.
            end_date (str): The end date for the data retrieval, in YYYY-mm-dd format.
            online (bool): Whether to fetch data online or offline.

        Returns:
            str: The stock stats indicator for the specified symbol and indicator.
        """
        curr_date = datetime.strptime(curr_date, "%Y-%m-%d")
        curr_date = curr_date.strftime("%Y-%m-%d")

        try:
            indicator_value = StockstatsUtils.get_stock_stats(
                symbol,
                indicator,
                curr_date,
                end_date,
            )
        except Exception as e:
            print(
                f"Error getting stockstats indicator data for indicator {indicator} on {curr_date}: {e}"
            )
            return ""

        return str(indicator_value)


if __name__ == "__main__":
    service = StockstatsService()
    print(
        service.get_stock_stats_indicators_window(
            "AAPL", "close_50_sma", "2025-08-25", 30, online=True
        )
    )
