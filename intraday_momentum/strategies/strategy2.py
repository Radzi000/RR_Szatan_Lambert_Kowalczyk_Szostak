"""Strategy 2 — EMA Trend Filter.

Adds a 100-period EMA as a trend confirmation filter. Entries require
alignment between the breakout direction and the EMA trend, reducing
false breakouts in ranging markets.
"""

from __future__ import annotations

import pandas as pd

from .base import BaseStrategy, Signal


class Strategy2(BaseStrategy):
    """Intraday momentum with EMA trend filter.

    Parameters
    ----------
    lookback : int
        Lookback period in days.
    vol_target : float
        Daily volatility target.
    entry_interval : int
        Minutes between entry checks.
    ema_period : int
        Period for the exponential moving average filter.
    """

    def __init__(
        self,
        lookback: int = 14,
        vol_target: float = 0.02,
        entry_interval: int = 30,
        ema_period: int = 100,
    ) -> None:
        super().__init__(lookback=lookback, vol_target=vol_target)
        self.entry_interval = entry_interval
        self.ema_period = ema_period

    def generate_signals(
        self,
        daily_data: pd.DataFrame,
        minute_data: pd.DataFrame,
    ) -> list[Signal]:
        """Run strategy 2 with EMA confirmation.

        Parameters
        ----------
        daily_data : pd.DataFrame
            Daily OHLCV for volatility estimation.
        minute_data : pd.DataFrame
            Minute-bar OHLCV for signal generation.

        Returns
        -------
        list[Signal]
            Ordered list of trading signals.
        """
        signals: list[Signal] = []

        daily_closes = daily_data["Close"].values
        daily_returns = [
            daily_closes[i] / daily_closes[i - 1] - 1 for i in range(1, len(daily_closes))
        ]

        # Compute EMA on minute close prices
        minute_data = minute_data.copy()
        minute_data["ema"] = minute_data["Close"].ewm(span=self.ema_period, adjust=False).mean()
        minute_data["date"] = minute_data.index.date
        trading_days = minute_data.groupby("date")

        position = 0
        yesterdays_close: float | None = None

        for _day_date, day_bars in trading_days:
            if day_bars.empty:
                continue

            todays_open: float | None = None
            cumulative_vp = 0.0
            cumulative_vol = 0.0

            for ts, bar in day_bars.iterrows():
                current_price = bar["Close"]
                ema_val = bar["ema"]
                current_time = ts.time()
                time_key = current_time.strftime("%H:%M")
                hour, minute = current_time.hour, current_time.minute

                if "Volume" in bar and bar["Volume"] > 0:
                    typical_price = (bar["High"] + bar["Low"] + bar["Close"]) / 3
                    cumulative_vp += typical_price * bar["Volume"]
                    cumulative_vol += bar["Volume"]
                vwap_val = cumulative_vp / cumulative_vol if cumulative_vol > 0 else current_price

                if hour == 9 and minute == 31:
                    todays_open = bar["Open"]

                if todays_open is None or yesterdays_close is None:
                    continue

                recent_returns = daily_returns[-(self.lookback) :]
                if len(recent_returns) < self.lookback:
                    continue

                sigma = self._compute_minute_sigma(time_key)
                current_move = abs(current_price / todays_open - 1)
                self._update_minute_stats(time_key, current_move)

                if sigma == 0:
                    continue

                upper_bound = max(todays_open, yesterdays_close) * (1 + sigma)
                lower_bound = min(todays_open, yesterdays_close) * (1 - sigma)

                if hour == 15 and minute >= 58:
                    if position != 0:
                        signals.append(Signal(ts, 0, reason="EOD exit"))
                        position = 0
                    continue

                if minute % self.entry_interval == 0:
                    if position == 0:
                        leverage = self.calculate_dynamic_leverage(recent_returns)
                        if leverage == 0:
                            continue
                        # Require EMA + VWAP confirmation for entry
                        if (
                            current_price > upper_bound
                            and current_price > vwap_val
                            and current_price > ema_val
                        ):
                            signals.append(Signal(ts, 1, leverage, "breakout + EMA/VWAP long"))
                            position = 1
                        elif (
                            current_price < lower_bound
                            and current_price < vwap_val
                            and current_price < ema_val
                        ):
                            signals.append(Signal(ts, -1, leverage, "breakout + EMA/VWAP short"))
                            position = -1
                    else:
                        if position == 1 and current_price < max(upper_bound, vwap_val):
                            signals.append(Signal(ts, 0, reason="long exit"))
                            position = 0
                        elif position == -1 and current_price > min(lower_bound, vwap_val):
                            signals.append(Signal(ts, 0, reason="short exit"))
                            position = 0

            if not day_bars.empty:
                yesterdays_close = day_bars.iloc[-1]["Close"]

        return signals
