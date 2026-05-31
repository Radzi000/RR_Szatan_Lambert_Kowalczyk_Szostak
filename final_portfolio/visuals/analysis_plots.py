"""Analytical plots: grid search heatmaps, ACF bar chart, drawdown comparison."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns


# ── 1. Grid search heatmaps ───────────────────────────────────────────────────

def plot_grid_search_heatmaps(
    kelly_results: pd.DataFrame,
    markowitz_results: pd.DataFrame,
    output_path: Path | None = None,
) -> None:
    """Side-by-side heatmaps of Sharpe ratio across lookback × rebalancing grids.

    Parameters
    ----------
    kelly_results : pd.DataFrame
        Output of grid_search_kelly(). Must have columns:
        lookback, rebalancing_days, sharpe_ratio.
    markowitz_results : pd.DataFrame
        Output of grid_search_markowitz(). Must have columns:
        lookback_days, rebalancing_days, sharpe_ratio.
    output_path : Path | None
        If provided, saves PNG. If None, displays on screen.
    """
    sns.set_theme(style="white")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Kelly heatmap
    kelly_pivot = kelly_results.pivot(
        index="lookback", columns="rebalancing_days", values="sharpe_ratio"
    )
    kelly_pivot = kelly_pivot.sort_index(ascending=False)

    sns.heatmap(
        kelly_pivot,
        ax=axes[0],
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        center=0,
        linewidths=0.5,
        cbar_kws={"label": "Sharpe ratio"},
    )
    axes[0].set_title("Kelly — grid search (train Sharpe)", fontsize=13, fontweight="bold")
    axes[0].set_xlabel("Rebalancing interval (days)", fontsize=10)
    axes[0].set_ylabel("Lookback (trades)", fontsize=10)

    # Markowitz heatmap
    mvo_pivot = markowitz_results.pivot(
        index="lookback_days", columns="rebalancing_days", values="sharpe_ratio"
    )
    mvo_pivot = mvo_pivot.sort_index(ascending=False)

    sns.heatmap(
        mvo_pivot,
        ax=axes[1],
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        center=0,
        linewidths=0.5,
        cbar_kws={"label": "Sharpe ratio"},
    )
    axes[1].set_title("Markowitz — grid search (train Sharpe)", fontsize=13, fontweight="bold")
    axes[1].set_xlabel("Rebalancing interval (days)", fontsize=10)
    axes[1].set_ylabel("Lookback window (calendar days)", fontsize=10)

    fig.suptitle(
        "Grid search: Sharpe ratio by lookback × rebalancing (train split)",
        fontsize=14, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    _save_or_show(fig, output_path)


# ── 2. ACF bar chart ──────────────────────────────────────────────────────────

def plot_acf_bars(
    acf_df: pd.DataFrame,
    output_path: Path | None = None,
) -> None:
    """Horizontal bar chart of lag-1 trade autocorrelation per instrument.

    Bars are coloured by interpretation:
        green  = momentum (ACF > 0.05)
        red    = mean-reversion (ACF < -0.05)
        grey   = independent

    Parameters
    ----------
    acf_df : pd.DataFrame
        Output of compute_trade_autocorrelations(). Must have columns:
        instrument, lag1_acf, interpretation.
    output_path : Path | None
        If provided, saves PNG. If None, displays on screen.
    """
    df = acf_df.sort_values("lag1_acf", ascending=True).reset_index(drop=True)

    color_map = {
        "momentum":       "#2ca02c",   # green
        "mean_reversion": "#d62728",   # red
        "independent":    "#aec7e8",   # light blue
    }
    colors = df["interpretation"].map(color_map).fillna("#aec7e8")

    # Short label: "Strategy3 / Exit | NVDA" → "S3 Exit | NVDA"
    def shorten(name: str) -> str:
        try:
            strat, asset = name.split("|")
            strat = strat.strip()
            # e.g. "Strategy3 / Exit Confirmation" → "S3·Exit"
            num = strat.split("/")[0].strip().replace("Strategy", "S")
            short_strat = strat.split("/")[1].strip().split()[0] if "/" in strat else strat
            return f"{num}·{short_strat} | {asset.strip()}"
        except Exception:
            return name

    labels = df["instrument"].apply(shorten)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 11))

    bars = ax.barh(labels, df["lag1_acf"], color=colors, edgecolor="white", linewidth=0.4)

    ax.axvline(0, color="black", linewidth=0.8)
    ax.axvline(0.05,  color="green", linewidth=0.8, linestyle="--", alpha=0.5, label="Momentum threshold (+0.05)")
    ax.axvline(-0.05, color="red",   linewidth=0.8, linestyle="--", alpha=0.5, label="Mean-rev threshold (−0.05)")

    ax.set_xlabel("Lag-1 autocorrelation of trade returns", fontsize=11)
    ax.set_title(
        "Trade dependency: lag-1 autocorrelation per instrument (train split)",
        fontsize=13, fontweight="bold",
    )

    # Legend patches
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#2ca02c", label="Momentum (ACF > 0.05)"),
        Patch(facecolor="#d62728", label="Mean-reversion (ACF < −0.05)"),
        Patch(facecolor="#aec7e8", label="Independent"),
    ]
    ax.legend(handles=legend_elements, fontsize=9, loc="lower right")

    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    _save_or_show(fig, output_path)


# ── 3. Drawdown comparison ────────────────────────────────────────────────────

def plot_drawdown_comparison(
    val_curves: dict[str, pd.Series],
    output_path: Path | None = None,
) -> None:
    """Plot portfolio drawdown curves for the validation period.

    Drawdown at each bar = (current value − running peak) / running peak × 100.

    Parameters
    ----------
    val_curves : dict[str, pd.Series]
        Equity curves for the validation period.
        Keys: "Equal-weight", "Kelly", "Markowitz".
    output_path : Path | None
        If provided, saves PNG. If None, displays on screen.
    """
    method_styles = {
        "Equal-weight": {"color": "black",     "linestyle": "-",  "linewidth": 2.0},
        "Kelly":        {"color": "steelblue", "linestyle": "--", "linewidth": 2.0},
        "Markowitz":    {"color": "tomato",    "linestyle": "-.", "linewidth": 2.0},
    }

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(13, 5))

    for method, curve in val_curves.items():
        peak = curve.expanding().max()
        drawdown = (curve - peak) / peak * 100
        max_dd = drawdown.min()

        style = method_styles.get(method, {"color": "purple", "linestyle": "-", "linewidth": 1.8})
        label = f"{method}  (max DD = {max_dd:.1f}%)"
        ax.plot(drawdown.index, drawdown.values, label=label, **style)

    ax.axhline(0, color="grey", linewidth=0.8, linestyle=":")

    ax.set_title("Drawdown comparison — validation period (2024–2025)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Drawdown (%)", fontsize=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.legend(fontsize=10, loc="lower left")

    fig.tight_layout()
    _save_or_show(fig, output_path)


# ── Helper ────────────────────────────────────────────────────────────────────

def _save_or_show(fig: plt.Figure, output_path: Path | None) -> None:
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Chart saved: {output_path}")
    else:
        plt.show()
    plt.close(fig)
