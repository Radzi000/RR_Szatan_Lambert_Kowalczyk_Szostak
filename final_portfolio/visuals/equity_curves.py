"""Equity curve plots for the final_portfolio layer."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

from final_portfolio.equal_weight import (
    DEFAULT_EQUITY_CURVES,
    equity_curve_from_returns,
    equal_weight_returns,
    load_equity_curves,
)

_INITIAL_CAPITAL = 100_000.0

# Consistent colour/style mapping used across all plot functions
_METHOD_STYLES: dict[str, dict] = {
    "Equal-weight": {"color": "black",     "linestyle": "-",  "linewidth": 2.2},
    "Kelly":        {"color": "steelblue", "linestyle": "--", "linewidth": 2.0},
    "Markowitz":    {"color": "tomato",    "linestyle": "-.", "linewidth": 2.0},
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _fmt_usd(ax: plt.Axes) -> None:
    """Format y-axis ticks as $123,456."""
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))


# ── Individual-strategy overview ─────────────────────────────────────────────

def plot_equal_weight(
    csv_path: Path = DEFAULT_EQUITY_CURVES,
    split: str = "train",
    output_path: Path | None = None,
) -> None:
    """Plot individual (strategy, asset) equity curves alongside the equal-weight portfolio.

    Parameters
    ----------
    csv_path : Path
        Path to equity_curves_our_strats.csv.
    split : str
        "train" or "validation".
    output_path : Path | None
        If provided, saves PNG. If None, displays on screen.
    """
    returns_wide = load_equity_curves(csv_path, split=split)
    portfolio_returns = equal_weight_returns(returns_wide)

    strategy_curves = {
        name: equity_curve_from_returns(returns_wide[name].fillna(0), _INITIAL_CAPITAL)
        for name in returns_wide.columns
    }
    portfolio_curve = equity_curve_from_returns(portfolio_returns, _INITIAL_CAPITAL)

    sns.set_theme(style="whitegrid", palette="deep")
    fig, ax = plt.subplots(figsize=(13, 6))

    colors = sns.color_palette("muted", len(strategy_curves))
    for (name, curve), color in zip(strategy_curves.items(), colors):
        short = name.split("|")[0].strip()
        ax.plot(curve.index, curve.values, color=color, linewidth=0.8, alpha=0.45, label=short)

    ax.plot(portfolio_curve.index, portfolio_curve.values,
            color="black", linewidth=2.4, label="Equal-weight", zorder=5)
    ax.axhline(_INITIAL_CAPITAL, color="grey", linestyle="--", linewidth=0.8, label="Initial capital")

    ax.set_title(f"Individual instrument curves and equal-weight portfolio ({split})",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Portfolio value ($)", fontsize=11)
    _fmt_usd(ax)

    # Deduplicate legend labels (35 instruments → too many)
    handles, labels = ax.get_legend_handles_labels()
    seen: set[str] = set()
    unique = [(h, l) for h, l in zip(handles, labels) if not (l in seen or seen.add(l))]  # type: ignore[func-returns-value]
    ax.legend(*zip(*unique), fontsize=8, loc="upper left", ncol=2)

    fig.tight_layout()
    _save_or_show(fig, output_path)


# ── Two-panel train / validation comparison ───────────────────────────────────

def plot_method_comparison(
    train_curves: dict[str, pd.Series],
    val_curves: dict[str, pd.Series],
    train_metrics: dict[str, dict],
    val_metrics: dict[str, dict],
    output_path: Path | None = None,
) -> None:
    """Side-by-side train and validation equity curve comparison.

    Each panel shows three methods: Equal-weight, Kelly, Markowitz.
    Legend entries include Sharpe ratio and total return for each method.

    Parameters
    ----------
    train_curves : dict[str, pd.Series]
        Equity curves for the training period. Keys: "Equal-weight", "Kelly", "Markowitz".
    val_curves : dict[str, pd.Series]
        Equity curves for the validation period. Same keys.
    train_metrics : dict[str, dict]
        compute_metrics output per method for the training period.
    val_metrics : dict[str, dict]
        compute_metrics output per method for the validation period.
    output_path : Path | None
        If provided, saves PNG. If None, displays on screen.
    """
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=False)

    for ax, curves, metrics, period in [
        (axes[0], train_curves, train_metrics, "Train"),
        (axes[1], val_curves, val_metrics, "Validation"),
    ]:
        ax.axhline(_INITIAL_CAPITAL, color="grey", linestyle=":", linewidth=1.0, zorder=1)

        for method, curve in curves.items():
            style = _METHOD_STYLES.get(method, {"color": "purple", "linestyle": "-", "linewidth": 1.8})
            m = metrics.get(method, {})
            sharpe = m.get("sharpe_ratio", float("nan"))
            ret = m.get("total_return_pct", float("nan"))
            label = f"{method}  |  Sharpe {sharpe:.2f}  |  +{ret:.1f}%"

            ax.plot(curve.index, curve.values, label=label, **style)

        ax.set_title(f"{period} period", fontsize=13, fontweight="bold")
        ax.set_xlabel("Date", fontsize=10)
        ax.set_ylabel("Portfolio value ($)", fontsize=10)
        _fmt_usd(ax)
        ax.legend(fontsize=9, loc="upper left")

    fig.suptitle(
        "Portfolio comparison — Equal-weight vs. Kelly vs. Markowitz",
        fontsize=14, fontweight="bold", y=1.01,
    )
    fig.tight_layout()
    _save_or_show(fig, output_path)


# ── Single-timeline plot with train/validation split marker ──────────────────

def plot_full_timeline(
    train_curves: dict[str, pd.Series],
    val_curves: dict[str, pd.Series],
    output_path: Path | None = None,
) -> None:
    """Plot all methods on a single timeline, rescaling validation to continue from train end.

    A vertical dashed line marks the train/validation boundary.
    Each curve is rebased so it starts at $100,000 on 2020-01-01 and grows continuously.

    Parameters
    ----------
    train_curves : dict[str, pd.Series]
        Equity curves (starting at $100K) for the training period.
    val_curves : dict[str, pd.Series]
        Equity curves (starting at $100K) for the validation period.
    output_path : Path | None
        If provided, saves PNG. If None, displays on screen.
    """
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(15, 6))

    split_date = None

    for method in train_curves:
        style = _METHOD_STYLES.get(method, {"color": "purple", "linestyle": "-", "linewidth": 1.8})
        t_curve = train_curves[method]
        v_curve = val_curves.get(method)

        # Rescale validation so it continues from the end of train
        if v_curve is not None and len(t_curve) > 0:
            train_end_val = float(t_curve.iloc[-1])
            scale = train_end_val / _INITIAL_CAPITAL
            v_scaled = v_curve * scale
            full_curve = pd.concat([t_curve, v_scaled])
            split_date = t_curve.index[-1]
        else:
            full_curve = t_curve

        ax.plot(full_curve.index, full_curve.values, label=method, **style)

    if split_date is not None:
        ax.axvline(split_date, color="grey", linestyle="--", linewidth=1.2, label="Train / Val split")
        ax.text(split_date, ax.get_ylim()[1], " Validation →", fontsize=9,
                color="grey", va="top", ha="left")

    ax.axhline(_INITIAL_CAPITAL, color="grey", linestyle=":", linewidth=0.8)
    ax.set_title("Full timeline — portfolio value from 2020 to 2025", fontsize=13, fontweight="bold")
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Portfolio value ($)", fontsize=10)
    _fmt_usd(ax)
    ax.legend(fontsize=10, loc="upper left")

    fig.tight_layout()
    _save_or_show(fig, output_path)


# ── Internal helper ───────────────────────────────────────────────────────────

def _save_or_show(fig: plt.Figure, output_path: Path | None) -> None:
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Chart saved: {output_path}")
    else:
        plt.show()
    plt.close(fig)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from final_portfolio.equal_weight import run_equal_weight
    from final_portfolio.kelly import run_kelly_portfolio
    from final_portfolio.markowitz import run_markowitz_portfolio

    repo_root = Path(__file__).parents[2]
    csv_path = DEFAULT_EQUITY_CURVES
    fig_dir = repo_root / "outputs" / "figures"

    KELLY_LB, KELLY_RB = 50, 30          # example values — run run_report.py for grid-search-selected params
    MARKOWITZ_LB, MARKOWITZ_RB = 90, 30  # example values — run run_report.py for grid-search-selected params

    print("Computing portfolio equity curves...")

    eq_train,  eq_tm  = run_equal_weight(csv_path, split="train")
    eq_val,    eq_vm  = run_equal_weight(csv_path, split="validation")

    kelly_train,  kelly_tm,  _ = run_kelly_portfolio(csv_path, KELLY_LB, KELLY_RB, split="train")
    kelly_val,    kelly_vm,  _ = run_kelly_portfolio(csv_path, KELLY_LB, KELLY_RB, split="validation")

    mvo_train, mvo_tm, _ = run_markowitz_portfolio(csv_path, MARKOWITZ_LB, MARKOWITZ_RB, split="train")
    mvo_val,   mvo_vm, _ = run_markowitz_portfolio(csv_path, MARKOWITZ_LB, MARKOWITZ_RB, split="validation")

    print("\n=== Results summary ===")
    for name, tm, vm in [
        ("Equal-weight", eq_tm, eq_vm),
        (f"Kelly(lb={KELLY_LB}t,rb={KELLY_RB}d)", kelly_tm, kelly_vm),
        (f"Markowitz(lb={MARKOWITZ_LB}d,rb={MARKOWITZ_RB}d)", mvo_tm, mvo_vm),
    ]:
        print(f"{name:45s} Train: Sharpe={tm['sharpe_ratio']:.2f} Ret={tm['total_return_pct']:+.1f}%"
              f"  |  Val: Sharpe={vm['sharpe_ratio']:.2f} Ret={vm['total_return_pct']:+.1f}%")

    train_curves = {"Equal-weight": eq_train, "Kelly": kelly_train, "Markowitz": mvo_train}
    val_curves   = {"Equal-weight": eq_val,   "Kelly": kelly_val,   "Markowitz": mvo_val}
    train_metrics = {"Equal-weight": eq_tm, "Kelly": kelly_tm, "Markowitz": mvo_tm}
    val_metrics   = {"Equal-weight": eq_vm, "Kelly": kelly_vm, "Markowitz": mvo_vm}

    # 1. Two-panel side-by-side comparison
    plot_method_comparison(
        train_curves, val_curves, train_metrics, val_metrics,
        output_path=fig_dir / "final_portfolio_comparison.png",
    )

    # 2. Single continuous timeline
    plot_full_timeline(
        train_curves, val_curves,
        output_path=fig_dir / "final_portfolio_timeline.png",
    )

    # 3. Individual strategy overview (train)
    plot_equal_weight(
        csv_path=csv_path,
        split="train",
        output_path=fig_dir / "final_portfolio_equal_weight_train.png",
    )

    print("\nDone. Figures saved to:", fig_dir)
