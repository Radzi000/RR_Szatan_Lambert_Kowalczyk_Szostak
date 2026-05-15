"""Visualization utilities for strategy analysis.

Creates charts for equity curves, drawdowns, trade distributions,
and other strategy performance visualizations.
"""

from .plots import (
    plot_drawdown,
    plot_equity_curve,
    plot_metrics_comparison,
    plot_monthly_returns,
    plot_optimization_convergence,
    plot_strategy_comparison,
    plot_trade_returns,
)

__all__ = [
    "plot_equity_curve",
    "plot_drawdown",
    "plot_trade_returns",
    "plot_monthly_returns",
    "plot_strategy_comparison",
    "plot_metrics_comparison",
    "plot_optimization_convergence",
]
