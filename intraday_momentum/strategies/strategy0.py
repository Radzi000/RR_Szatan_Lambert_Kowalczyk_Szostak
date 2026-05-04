"""Strategy 0 — Baseline Intraday Momentum.

Original QuantConnect implementation by blackswan-quants, converted
for local backtesting. Uses minute-of-day sigma bands with VWAP-based
exit logic and volatility-targeted position sizing.

Key features:
- Breakout entry when price exceeds sigma band around open/prev-close.
- VWAP trailing-stop exit.
- 30-minute entry check interval.
- Dynamic leverage via target-vol / realized-vol.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseStrategy, Signal


class Strategy0(BaseStrategy):
    """Baseline intraday momentum with VWAP exit.

    Parameters
    ----------
    lookback : int
        Lookback period in days for volatility and sigma estimation.
    vol_target : float
        Daily volatility target for leverage calculation.
    entry_interval : int
        Minutes between entry checks (default 30).

    Examples
    --------
    >>> strat = Strategy0(lookback=14, vol_target=0.02)
    >>> signals = strat.generate_signals(daily_df, minute_df)
    """

    def __init__(
        self,
        lookback: int = 14,
        vol_target: float = 0.02,
        entry_interval: int = 30,
    ) -> None:
        super().__init__(lookback=lookback, vol_target=vol_target)
        self.entry_interval = entry_interval

    def generate_signals(
        self,
        daily_data: pd.DataFrame,
        minute_data: pd.DataFrame,
    ) -> list[Signal]:
        """Run strategy 0 on historical minute data.

        Parameters
        ----------
        daily_data : pd.DataFrame
            Daily OHLCV with ``Close`` column for volatility estimation.
        minute_data : pd.DataFrame
            Minute-bar OHLCV data (must contain ``Open``, ``Close`` columns).

        Returns
        -------
        list[Signal]
            Ordered list of entry and exit signals.
        """
        signals: list[Signal] = []

        # Compute daily returns for volatility
        daily_closes = daily_data["Close"].values
        daily_returns = []
        for i in range(1, len(daily_closes)):
            daily_returns.append(daily_closes[i] / daily_closes[i - 1] - 1)

        # Group minute data by trading day
        minute_data = minute_data.copy()
        minute_data["date"] = minute_data.index.date
        trading_days = minute_data.groupby("date")

        position = 0  # 1=long, -1=short, 0=flat
        yesterdays_close: float | None = None

        for day_date, day_bars in trading_days:
            if day_bars.empty:
                continue

            todays_open: float | None = None
            # Compute VWAP for the day
            cumulative_vp = 0.0
            cumulative_vol = 0.0

            for ts, bar in day_bars.iterrows():
                current_price = bar["Close"]
                current_time = ts.time()
                time_key = current_time.strftime("%H:%M")
                hour, minute = current_time.hour, current_time.minute

                # Update running VWAP
                if "Volume" in bar and bar["Volume"] > 0:
                    typical_price = (bar["High"] + bar["Low"] + bar["Close"]) / 3
                    cumulative_vp += typical_price * bar["Volume"]
                    cumulative_vol += bar["Volume"]
                vwap_val = cumulative_vp / cumulative_vol if cumulative_vol > 0 else current_price

                # Set open at 9:31
                if self._is_market_open(hour, minute) and todays_open is None:
                    todays_open = bar["Open"]

                if todays_open is None or yesterdays_close is None:
                    continue

                # Need enough daily returns for vol calc
                recent_returns = daily_returns[-(self.lookback) :]
                if len(recent_returns) < self.lookback:
                    continue

                # Sigma bands
                sigma = self._compute_minute_sigma(time_key)
                current_move = abs(current_price / todays_open - 1)
                self._update_minute_stats(time_key, current_move)

                if sigma == 0:
                    continue

                upper_bound = max(todays_open, yesterdays_close) * (1 + sigma)
                lower_bound = min(todays_open, yesterdays_close) * (1 - sigma)

                # Exit at market close
                if self._is_market_close(hour, minute):
                    if position != 0:
                        signals.append(Signal(ts, 0, reason="EOD exit"))
                        position = 0
                    continue

                # Entry/exit every entry_interval minutes
                if minute % self.entry_interval == 0:
                    if position == 0:
                        leverage = self.calculate_dynamic_leverage(recent_returns)
                        if leverage == 0:
                            continue
                        if current_price > upper_bound:
                            signals.append(
                                Signal(ts, 1, leverage, "breakout above upper band")
                            )
                            position = 1
                        elif current_price < lower_bound:
                            signals.append(
                                Signal(ts, -1, leverage, "breakout below lower band")
                            )
                            position = -1
                    else:
                        if position == 1 and current_price < max(upper_bound, vwap_val):
                            signals.append(Signal(ts, 0, reason="long exit: price < VWAP/band"))
                            position = 0
                        elif position == -1 and current_price > min(lower_bound, vwap_val):
                            signals.append(Signal(ts, 0, reason="short exit: price > VWAP/band"))
                            position = 0

            # End of day
            if not day_bars.empty:
                yesterdays_close = day_bars.iloc[-1]["Close"]

        return signals
