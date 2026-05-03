"""Base strategy interface.

All intraday momentum strategies inherit from :class:`BaseStrategy`,
which defines the contract for signal generation and position sizing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Signal:
    """Trading signal produced by a strategy.

    Attributes
    ----------
    timestamp : pd.Timestamp
        Time the signal was generated.
    direction : int
        ``1`` for long, ``-1`` for short, ``0`` for flat / exit.
    leverage : float
        Target leverage (absolute value).
    reason : str
        Human-readable explanation of the signal.
    """

    timestamp: pd.Timestamp
    direction: int  # 1 = long, -1 = short, 0 = exit
    leverage: float = 1.0
    reason: str = ""


class BaseStrategy(ABC):
    """Abstract base class for intraday momentum strategies.

    Parameters
    ----------
    lookback : int
        Number of days for volatility and minute-stats lookback.
    vol_target : float
        Target daily volatility for position sizing (e.g. 0.02 = 2%).
    """

    def __init__(self, lookback: int = 14, vol_target: float = 0.02) -> None:
        self.lookback = lookback
        self.vol_target = vol_target
        self.daily_returns: list[float] = []
        self.minute_stats: dict[str, list[float]] = {}

    @abstractmethod
    def generate_signals(self, daily_data: pd.DataFrame, minute_data: pd.DataFrame) -> list[Signal]:
        """Run the strategy on historical data and return a list of signals.

        Parameters
        ----------
        daily_data : pd.DataFrame
            Daily OHLCV data for volatility estimation.
        minute_data : pd.DataFrame
            Minute-bar OHLCV data for signal generation.

        Returns
        -------
        list[Signal]
            Chronologically ordered list of trading signals.
        """

    def calculate_dynamic_leverage(self, recent_daily_returns: list[float]) -> float:
        """Compute leverage based on target volatility scaling.

        Parameters
        ----------
        recent_daily_returns : list[float]
            Recent daily returns (at least ``lookback`` entries).

        Returns
        -------
        float
            Leverage factor, capped at 2.0. Returns 0 if insufficient data.
        """
        if len(recent_daily_returns) < self.lookback:
            return 0.0
        current_vol = np.std(recent_daily_returns)
        if current_vol == 0:
            return 0.0
        return min(2.0, self.vol_target / current_vol)

    def _compute_minute_sigma(self, time_key: str) -> float:
        """Get average absolute move for a specific minute-of-day.

        Parameters
        ----------
        time_key : str
            Time key in ``"HH:MM"`` format.

        Returns
        -------
        float
            Mean absolute move, or 0 if no history.
        """
        moves = self.minute_stats.get(time_key, [])
        if not moves:
            return 0.0
        return float(np.mean(moves[-self.lookback :]))

    def _update_minute_stats(self, time_key: str, move: float) -> None:
        """Record an absolute move for a minute-of-day slot.

        Parameters
        ----------
        time_key : str
            Time key in ``"HH:MM"`` format.
        move : float
            Absolute price move relative to today's open.
        """
        if time_key not in self.minute_stats:
            self.minute_stats[time_key] = []
        self.minute_stats[time_key].append(move)
        # Keep only last N days
        if len(self.minute_stats[time_key]) > self.lookback:
            self.minute_stats[time_key] = self.minute_stats[time_key][-self.lookback :]
