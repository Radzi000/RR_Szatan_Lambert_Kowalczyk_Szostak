"""Publication-quality charts for strategy analysis.

Provides a set of standalone plotting functions that accept
:class:`~intraday_momentum.backtest.engine.BacktestResult` objects
and produce Matplotlib figures. All functions return the figure so
callers can further customise or save to disk.

Example
-------
>>> from intraday_momentum.visualization.plots import plot_equity_curve
>>> fig = plot_equity_curve(result, title="Strategy 0 — Equity")
>>> fig.savefig("equity.png", dpi=150)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from ..backtest.engine import BacktestResult
    from ..optimization.tuner import TunerResult

# ── Style defaults ──────────────────────────────────────────────

_PALETTE = sns.color_palette("deep")
_LONG_COLOR = _PALETTE[2]   # green
_SHORT_COLOR = _PALETTE[3]  # red
_EQUITY_COLOR = _PALETTE[0] # blue
_BENCH_COLOR = _PALETTE[7]  # grey


def _apply_style(ax: plt.Axes, title: str, xlabel: str, ylabel: str) -> None:
    """Apply a consistent look to an axes object."""
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.tick_params(labelsize=9)
    ax.grid(True, alpha=0.3, linestyle="--")
    sns.despine(ax=ax)


# ── Equity curve ────────────────────────────────────────────────

def plot_equity_curve(
    result: BacktestResult,
    *,
    title: str = "Equity Curve",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot portfolio value over time.

    Parameters
    ----------
    result : BacktestResult
        Output of :meth:`BacktestEngine.run`.
    title : str
        Chart title.
    figsize : tuple[float, float]
        Figure dimensions in inches.

    Returns
    -------
    Figure
        Matplotlib figure.
    """
    fig, ax = plt.subplots(figsize=figsize)
    curve = result.equity_curve
    ax.plot(curve.index, curve.values, color=_EQUITY_COLOR, linewidth=1.2)
    ax.axhline(result.initial_capital, color=_BENCH_COLOR, linestyle="--", linewidth=0.8, label="Initial capital")
    ax.fill_between(
        curve.index,
        result.initial_capital,
        curve.values,
        where=curve.values >= result.initial_capital,
        alpha=0.15,
        color=_LONG_COLOR,
    )
    ax.fill_between(
        curve.index,
        result.initial_capital,
        curve.values,
        where=curve.values < result.initial_capital,
        alpha=0.15,
        color=_SHORT_COLOR,
    )
    ax.legend(fontsize=9)
    _apply_style(ax, title, "Date", "Portfolio Value ($)")
    fig.tight_layout()
    return fig


# ── Drawdown ────────────────────────────────────────────────────

def plot_drawdown(
    result: BacktestResult,
    *,
    title: str = "Underwater Curve (Drawdown)",
    figsize: tuple[float, float] = (12, 4),
) -> Figure:
    """Plot drawdown (underwater) curve as percentage from peak.

    Parameters
    ----------
    result : BacktestResult
        Output of :meth:`BacktestEngine.run`.
    title : str
        Chart title.
    figsize : tuple[float, float]
        Figure dimensions.

    Returns
    -------
    Figure
        Matplotlib figure.
    """
    fig, ax = plt.subplots(figsize=figsize)
    curve = result.equity_curve
    peak = curve.expanding().max()
    drawdown = (curve - peak) / peak * 100

    ax.fill_between(drawdown.index, 0, drawdown.values, color=_SHORT_COLOR, alpha=0.4)
    ax.plot(drawdown.index, drawdown.values, color=_SHORT_COLOR, linewidth=0.8)
    _apply_style(ax, title, "Date", "Drawdown (%)")
    fig.tight_layout()
    return fig


# ── Trade distribution ──────────────────────────────────────────

def plot_trade_returns(
    result: BacktestResult,
    *,
    title: str = "Trade Return Distribution",
    bins: int = 40,
    figsize: tuple[float, float] = (10, 5),
) -> Figure:
    """Histogram of per-trade return percentages.

    Parameters
    ----------
    result : BacktestResult
        Output of :meth:`BacktestEngine.run`.
    title : str
        Chart title.
    bins : int
        Number of histogram bins.
    figsize : tuple[float, float]
        Figure dimensions.

    Returns
    -------
    Figure
        Matplotlib figure.
    """
    fig, ax = plt.subplots(figsize=figsize)
    returns = [t.return_pct for t in result.trades]
    if not returns:
        ax.text(0.5, 0.5, "No trades", transform=ax.transAxes, ha="center", fontsize=14)
        return fig

    colors = [_LONG_COLOR if r > 0 else _SHORT_COLOR for r in returns]
    ax.hist(returns, bins=bins, color=_EQUITY_COLOR, edgecolor="white", alpha=0.7)
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
    mean_ret = np.mean(returns)
    ax.axvline(mean_ret, color=_PALETTE[1], linewidth=1.2, linestyle="-", label=f"Mean: {mean_ret:.2f}%")
    ax.legend(fontsize=9)
    _apply_style(ax, title, "Return (%)", "Frequency")
    fig.tight_layout()
    return fig


# ── Monthly returns heatmap ─────────────────────────────────────

def plot_monthly_returns(
    result: BacktestResult,
    *,
    title: str = "Monthly Returns (%)",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Heatmap of monthly returns.

    Parameters
    ----------
    result : BacktestResult
        Output of :meth:`BacktestEngine.run`.
    title : str
        Chart title.
    figsize : tuple[float, float]
        Figure dimensions.

    Returns
    -------
    Figure
        Matplotlib figure.
    """
    fig, ax = plt.subplots(figsize=figsize)
    curve = result.equity_curve
    monthly = curve.resample("ME").last().pct_change().dropna() * 100

    if monthly.empty:
        ax.text(0.5, 0.5, "Insufficient data", transform=ax.transAxes, ha="center", fontsize=14)
        return fig

    df = pd.DataFrame({"return": monthly.values}, index=monthly.index)
    df["year"] = df.index.year
    df["month"] = df.index.month
    pivot = df.pivot_table(values="return", index="year", columns="month", aggfunc="sum")
    pivot.columns = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(pivot.columns)]

    sns.heatmap(
        pivot,
        annot=True,
        fmt=".1f",
        center=0,
        cmap="RdYlGn",
        linewidths=0.5,
        ax=ax,
        cbar_kws={"label": "Return (%)"},
    )
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_ylabel("")
    fig.tight_layout()
    return fig


# ── Strategy comparison ─────────────────────────────────────────

def plot_strategy_comparison(
    results: dict[str, BacktestResult],
    *,
    title: str = "Strategy Comparison — Equity Curves",
    figsize: tuple[float, float] = (12, 6),
) -> Figure:
    """Overlay equity curves from multiple strategies.

    Parameters
    ----------
    results : dict[str, BacktestResult]
        Mapping of strategy name → backtest result.
    title : str
        Chart title.
    figsize : tuple[float, float]
        Figure dimensions.

    Returns
    -------
    Figure
        Matplotlib figure.
    """
    fig, ax = plt.subplots(figsize=figsize)
    palette = sns.color_palette("husl", len(results))

    for (name, res), color in zip(results.items(), palette):
        curve = res.equity_curve
        label = f"{name} ({res.total_return:+.1f}%)"
        ax.plot(curve.index, curve.values, color=color, linewidth=1.2, label=label)

    ax.axhline(
        list(results.values())[0].initial_capital,
        color=_BENCH_COLOR,
        linestyle="--",
        linewidth=0.8,
    )
    ax.legend(fontsize=9, loc="upper left")
    _apply_style(ax, title, "Date", "Portfolio Value ($)")
    fig.tight_layout()
    return fig


# ── Metrics summary bar chart ───────────────────────────────────

def plot_metrics_comparison(
    results: dict[str, BacktestResult],
    *,
    metrics: list[str] | None = None,
    title: str = "Strategy Metrics Comparison",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Grouped bar chart comparing key metrics across strategies.

    Parameters
    ----------
    results : dict[str, BacktestResult]
        Mapping of strategy name → backtest result.
    metrics : list[str] | None
        Which metrics to include. Defaults to Sharpe, return,
        win rate, and max drawdown.
    title : str
        Chart title.
    figsize : tuple[float, float]
        Figure dimensions.

    Returns
    -------
    Figure
        Matplotlib figure.
    """
    if metrics is None:
        metrics = ["sharpe_ratio", "total_return_pct", "win_rate", "max_drawdown_pct"]

    data: dict[str, list[float]] = {m: [] for m in metrics}
    names = list(results.keys())

    for res in results.values():
        s = res.summary()
        for m in metrics:
            data[m].append(s.get(m, 0.0))

    n_metrics = len(metrics)
    n_strats = len(names)
    x = np.arange(n_metrics)
    width = 0.8 / n_strats
    palette = sns.color_palette("husl", n_strats)

    fig, ax = plt.subplots(figsize=figsize)
    for i, (name, color) in enumerate(zip(names, palette)):
        vals = [data[m][i] for m in metrics]
        offset = (i - n_strats / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=name, color=color, alpha=0.85)

    labels = [m.replace("_", " ").title() for m in metrics]
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.legend(fontsize=9)
    _apply_style(ax, title, "", "Value")
    fig.tight_layout()
    return fig


# ── Optimization convergence ────────────────────────────────────

def plot_optimization_convergence(
    tuner_result: TunerResult,
    *,
    title: str = "CMA-ES Optimization Convergence",
    figsize: tuple[float, float] = (10, 5),
) -> Figure:
    """Plot per-generation best and mean objective over time.

    Parameters
    ----------
    tuner_result : TunerResult
        Output of :meth:`StrategyTuner.run`.
    title : str
        Chart title.
    figsize : tuple[float, float]
        Figure dimensions.

    Returns
    -------
    Figure
        Matplotlib figure.
    """
    fig, ax = plt.subplots(figsize=figsize)
    history = tuner_result.history
    gens = [h["generation"] for h in history]
    bests = [h["cumulative_best"] for h in history]
    means = [h["mean"] for h in history]

    ax.plot(gens, bests, color=_EQUITY_COLOR, linewidth=1.5, marker="o", markersize=4, label="Cumulative best")
    ax.plot(gens, means, color=_PALETTE[1], linewidth=1.0, linestyle="--", alpha=0.7, label="Generation mean")
    ax.fill_between(
        gens,
        [h["mean"] - h["std"] for h in history],
        [h["mean"] + h["std"] for h in history],
        alpha=0.15,
        color=_PALETTE[1],
    )
    ax.legend(fontsize=9)
    _apply_style(ax, title, "Generation", "Objective Value")
    fig.tight_layout()
    return fig
