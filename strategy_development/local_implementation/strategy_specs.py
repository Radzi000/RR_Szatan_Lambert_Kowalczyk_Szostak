"""Authoritative fixed strategy specifications for local experiments."""

from __future__ import annotations

from dataclasses import dataclass

from .strategies import Strategy0, Strategy1, Strategy2, Strategy3, Strategy4


@dataclass(frozen=True)
class StrategySpec:
    """Configuration for one deterministic strategy run."""

    label: str
    factory: type
    params: dict[str, int | float]


STRATEGY_SPECS = [
    StrategySpec("Strategy0 / Baseline", Strategy0, {"lookback": 14, "vol_target": 0.02}),
    StrategySpec(
        "Strategy1 / Asymmetric Intervals",
        Strategy1,
        {"lookback": 14, "vol_target": 0.02, "entry_interval": 30, "exit_interval": 5},
    ),
    StrategySpec(
        "Strategy2 / EMA Filter",
        Strategy2,
        {"lookback": 14, "vol_target": 0.02, "entry_interval": 30, "ema_period": 100},
    ),
    StrategySpec(
        "Strategy3 / Exit Confirmation",
        Strategy3,
        {
            "lookback": 14,
            "vol_target": 0.02,
            "entry_interval": 30,
            "exit_interval": 5,
            "exit_confirmation_bars": 4,
        },
    ),
    StrategySpec(
        "Strategy4 / EMA + Confirmation",
        Strategy4,
        {
            "lookback": 14,
            "vol_target": 0.02,
            "entry_interval": 30,
            "exit_interval": 5,
            "exit_confirmation_bars": 4,
            "ema_period": 100,
        },
    ),
]
