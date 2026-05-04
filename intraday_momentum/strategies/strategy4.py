"""Strategy 4 — EMA Filter + Exit Confirmation.

Combines Strategy 2's EMA trend filter with Strategy 3's exit
confirmation counter. Represents the most conservative variant with
dual entry confirmation (band breakout + EMA alignment) and delayed
exit execution.
"""

from __future__ import annotations

import pandas as pd

from .base import BaseStrategy, Signal


class Strategy4(BaseStrategy):
    """Intraday momentum with EMA filter and confirmed exits.

    Parameters
    ----------
    lookback : int
        Lookback period in days.
    vol_target : float
        Daily volatility target.
    entry_interval : int
        Minutes between entry checks.
    exit_interval : int
        Minutes between exit checks.
    exit_confirmation_bars : int
        Consecutive exit signals required.
    ema_period : int
        EMA period for trend filter.
    """

    def __init__(
        self,
        lookback: int = 14,
        vol_target: float = 0.02,
        entry_interval: int = 30,
        exit_interval: int = 5,
        exit_confirmation_bars: int = 4,
        ema_period: int = 100,
    ) -> None:
        super().__init__(lookback=lookback, vol_target=vol_target)
        self.entry_interval = entry_interval
        self.exit_interval = exit_interval
        self.exit_confirmation_bars = exit_confirmation_bars
        self.ema_period = ema_period

    def generate_signals(
        self,
        daily_data: pd.DataFrame,
        minute_data: pd.DataFrame,
    ) -> list[Signal]:
        """Run strategy 4 with EMA + confirmed exits.

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

        minute_data = minute_data.copy()
        minute_data["ema"] = minute_data["Close"].ewm(span=self.ema_period, adjust=False).mean()
        minute_data["date"] = minute_data.index.date
        trading_days = minute_data.groupby("date")

        position = 0
        yesterdays_close: float | None = None
        long_exit_counter = 0
        short_exit_counter = 0

        for _day_date, day_bars in trading_days:
            if day_bars.empty:
                continue

            todays_open: float | None = None
            cumulative_vp = 0.0
            cumulative_vol = 0.0
            long_exit_counter = 0
            short_exit_counter = 0

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

                if self._is_market_open(hour, minute) and todays_open is None:
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

                if self._is_market_close(hour, minute):
                    if position != 0:
                        signals.append(Signal(ts, 0, reason="EOD exit"))
                        position = 0
                    long_exit_counter = 0
                    short_exit_counter = 0
                    continue

                # Exit with confirmation
                if position != 0 and minute % self.exit_interval == 0:
                    if position == 1:
                        exit_level = max(upper_bound, vwap_val)
                        if current_price < exit_level:
                            long_exit_counter += 1
                        else:
                            long_exit_counter = 0
                        if long_exit_counter >= self.exit_confirmation_bars:
                            signals.append(Signal(ts, 0, reason="confirmed long exit"))
                            position = 0
                            long_exit_counter = 0
                            short_exit_counter = 0
                            continue
                    elif position == -1:
                        exit_level = min(lower_bound, vwap_val)
                        if current_price > exit_level:
                            short_exit_counter += 1
                        else:
                            short_exit_counter = 0
                        if short_exit_counter >= self.exit_confirmation_bars:
                            signals.append(Signal(ts, 0, reason="confirmed short exit"))
                            position = 0
                            long_exit_counter = 0
                            short_exit_counter = 0
                            continue

                # Entry with EMA confirmation
                if position == 0 and minute % self.entry_interval == 0:
                    leverage = self.calculate_dynamic_leverage(recent_returns)
                    if leverage == 0:
                        continue
                    if current_price > upper_bound and current_price > ema_val:
                        signals.append(Signal(ts, 1, leverage, "breakout + EMA long"))
                        position = 1
                        long_exit_counter = 0
                        short_exit_counter = 0
                    elif current_price < lower_bound and current_price < ema_val:
                        signals.append(Signal(ts, -1, leverage, "breakout + EMA short"))
                        position = -1
                        long_exit_counter = 0
                        short_exit_counter = 0

            if not day_bars.empty:
                yesterdays_close = day_bars.iloc[-1]["Close"]

        return signals
