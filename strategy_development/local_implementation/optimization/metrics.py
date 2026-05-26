"""Metrics used by Workstream C optimization and verification."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..backtest.engine import BacktestResult

PERIODS_PER_YEAR_15M = 252 * 26


@dataclass(frozen=True)
class MetricBundle:
    """Normalized metrics for one strategy run on one split."""

    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    hit_rate: float
    turnover: float
    trade_count: int
    average_trade_pnl: float
    exposure_time: float


def _equity_returns(result: BacktestResult) -> pd.Series:
    if result.equity_curve.empty:
        return pd.Series(dtype=float)
    return result.equity_curve.astype(float).pct_change().dropna()


def _max_drawdown_pct(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    peak = equity_curve.cummax()
    drawdown = (equity_curve / peak - 1.0) * 100.0
    return float(drawdown.min())


def _annualized_return_pct(result: BacktestResult) -> float:
    if result.equity_curve.empty or result.initial_capital <= 0:
        return 0.0
    start = result.equity_curve.index.min()
    end = result.equity_curve.index.max()
    elapsed_days = max((end - start).total_seconds() / 86400.0, 1.0)
    years = elapsed_days / 365.25
    growth = result.final_equity / result.initial_capital
    if growth <= 0:
        return -100.0
    return float((growth ** (1 / years) - 1.0) * 100.0)


def _turnover(result: BacktestResult, bar_count: int) -> float:
    if bar_count <= 0:
        return 0.0
    return float((2 * len(result.trades)) / bar_count)


def _exposure_time(result: BacktestResult, minute_data: pd.DataFrame) -> float:
    if minute_data.empty or not result.trades:
        return 0.0
    total_bars = len(minute_data)
    exposed = 0
    for trade in result.trades:
        exposed += int(
            ((minute_data.index >= trade.entry_time) & (minute_data.index <= trade.exit_time)).sum()
        )
    return float(min(exposed / total_bars, 1.0))


def compute_metric_bundle(result: BacktestResult, minute_data: pd.DataFrame) -> MetricBundle:
    """Compute deterministic verification metrics from a backtest result."""
    returns = _equity_returns(result)
    annualized_volatility = 0.0
    sharpe = 0.0
    sortino = 0.0
    if len(returns) > 1:
        returns_std = float(returns.std())
        if returns_std > 0:
            annualized_volatility = returns_std * np.sqrt(PERIODS_PER_YEAR_15M) * 100.0
            sharpe = float((returns.mean() / returns_std) * np.sqrt(PERIODS_PER_YEAR_15M))
        downside = returns[returns < 0]
        downside_std = float(downside.std()) if len(downside) > 1 else 0.0
        if downside_std > 0:
            sortino = float((returns.mean() / downside_std) * np.sqrt(PERIODS_PER_YEAR_15M))

    total_return = float(result.total_return)
    annualized_return = _annualized_return_pct(result)
    max_drawdown = _max_drawdown_pct(result.equity_curve.astype(float))
    calmar = float(annualized_return / abs(max_drawdown)) if abs(max_drawdown) > 1e-9 else 0.0
    average_trade_pnl = float(np.mean([trade.pnl for trade in result.trades])) if result.trades else 0.0

    return MetricBundle(
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_drawdown,
        calmar=calmar,
        hit_rate=float(result.win_rate),
        turnover=_turnover(result, len(minute_data)),
        trade_count=int(result.num_trades),
        average_trade_pnl=average_trade_pnl,
        exposure_time=_exposure_time(result, minute_data),
    )


def overfit_warning(
    *,
    baseline_validation_sharpe: float,
    optimized_train_sharpe: float,
    optimized_validation_sharpe: float,
) -> str:
    """Return a simple deterministic overfit warning label."""
    if optimized_validation_sharpe < baseline_validation_sharpe:
        return "validation_regression"
    if optimized_train_sharpe - optimized_validation_sharpe > 1.0:
        return "train_validation_gap"
    return "none"
