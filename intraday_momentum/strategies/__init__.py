"""Trading strategy implementations.

Contains intraday momentum strategies converted from QuantConnect
to work with local data sources (yfinance).

Available strategies:

- :class:`Strategy0` — Baseline with VWAP exit
- :class:`Strategy1` — Asymmetric entry/exit intervals
- :class:`Strategy2` — EMA trend filter
- :class:`Strategy3` — Exit confirmation counter
- :class:`Strategy4` — EMA filter + exit confirmation
"""

from .base import BaseStrategy, Signal
from .strategy0 import Strategy0
from .strategy1 import Strategy1
from .strategy2 import Strategy2
from .strategy3 import Strategy3
from .strategy4 import Strategy4

__all__ = [
    "BaseStrategy",
    "Signal",
    "Strategy0",
    "Strategy1",
    "Strategy2",
    "Strategy3",
    "Strategy4",
]
