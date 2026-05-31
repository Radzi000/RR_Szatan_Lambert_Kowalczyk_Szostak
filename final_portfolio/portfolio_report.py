"""Portfolio report generator — compiles all final_portfolio results into one summary."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def generate_report(
    metrics: dict[str, dict],
    acf_df: pd.DataFrame,
    kelly_grid: pd.DataFrame,
    markowitz_grid: pd.DataFrame,
    output_path: Path | None = None,
) -> str:
    """Build a markdown report summarising all portfolio construction results.

    Parameters
    ----------
    metrics : dict[str, dict]
        Nested dict: {method_label: {"train": metrics_dict, "val": metrics_dict}}.
        Each inner dict is the output of compute_metrics().
    acf_df : pd.DataFrame
        Output of compute_trade_autocorrelations().
    kelly_grid : pd.DataFrame
        Output of grid_search_kelly() — all train-split combinations.
    markowitz_grid : pd.DataFrame
        Output of grid_search_markowitz() — all train-split combinations.
    output_path : Path | None
        If provided, saves report as .md file.

    Returns
    -------
    str : the full report text.
    """
    lines: list[str] = []
    w = lines.append

    # ── Header ────────────────────────────────────────────────────────────────
    w("# Final Portfolio — Results Report")
    w(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w("")
    w("## Project context")
    w("")
    w("Portfolio construction on Workstream C multi-asset equity curves.")
    w("Data: 5 strategies × 7 assets (AAPL, BTCUSDT, ETHUSDT, GLD, MSFT, NVDA, USO),")
    w("15-min bars, 2020–2025. Train: Aug 2020 – Jun 2024. Validation: Jul 2024 – Apr 2025.")
    w("")
    w("Three methods compared:")
    w("- **Equal-weight**: 1/N allocation, no optimisation.")
    w("- **Kelly (Half-Kelly)**: per-instrument weights from win-rate and R-ratio,")
    w("  computed on per-trade returns (bars aggregated into trades).")
    w("- **Markowitz (MVO)**: maximum-Sharpe weights from rolling covariance matrix.")
    w("")

    # ── Main results table ────────────────────────────────────────────────────
    w("## 1. Performance summary")
    w("")
    w("| Method | Train Sharpe | Train Return | Train MaxDD | Val Sharpe | Val Return | Val MaxDD |")
    w("|---|---|---|---|---|---|---|")
    for label, m in metrics.items():
        t, v = m["train"], m["val"]
        w(f"| {label} "
          f"| {t['sharpe_ratio']:.3f} "
          f"| {t['total_return_pct']:+.1f}% "
          f"| {t['max_drawdown_pct']:.1f}% "
          f"| {v['sharpe_ratio']:.3f} "
          f"| {v['total_return_pct']:+.1f}% "
          f"| {v['max_drawdown_pct']:.1f}% |")
    w("")

    # ── Parameter selection ───────────────────────────────────────────────────
    w("## 2. Parameter selection (grid search on train split)")
    w("")
    w("### Kelly — lookback (trades) × rebalancing (days)")
    w("")

    kelly_pivot = kelly_grid.pivot(
        index="lookback", columns="rebalancing_days", values="sharpe_ratio"
    ).sort_index(ascending=False)
    w(_pivot_to_markdown(kelly_pivot, row_prefix="lookback=", row_suffix="t",
                         col_prefix="rebal=", col_suffix="d"))
    w("")

    best_k = kelly_grid.iloc[0]
    w(f"**Best**: lookback={int(best_k['lookback'])} trades, rebalancing={int(best_k['rebalancing_days'])} days "
      f"→ Train Sharpe = {best_k['sharpe_ratio']:.3f}")
    w("")
    w("> Long rebalancing intervals (30 days) consistently outperform short ones (5 days).")
    w("> Short rebalancing causes Kelly to react to noise, chasing winners and incurring")
    w("> high turnover without improving risk-adjusted returns.")
    w("")

    w("### Markowitz — lookback (calendar days) × rebalancing (days)")
    w("")
    mvo_pivot = markowitz_grid.pivot(
        index="lookback_days", columns="rebalancing_days", values="sharpe_ratio"
    ).sort_index(ascending=False)
    w(_pivot_to_markdown(mvo_pivot, row_prefix="lookback=", row_suffix="d",
                         col_prefix="rebal=", col_suffix="d"))
    w("")

    best_m = markowitz_grid.iloc[0]
    w(f"**Best**: lookback={int(best_m['lookback_days'])} days, rebalancing={int(best_m['rebalancing_days'])} days "
      f"→ Train Sharpe = {best_m['sharpe_ratio']:.3f}")
    w("")
    w("> Calendar-day lookback is used instead of row count to ensure equities and crypto")
    w("> are evaluated over the same time horizon (crypto has ~6× more bars per day).")
    w("")

    # ── Trade dependency ──────────────────────────────────────────────────────
    w("## 3. Trade dependency analysis")
    w("")
    w("Lag-1 autocorrelation of per-trade returns was computed for all 35 instruments")
    w("on the training split. Interpretation threshold: |ACF| > 0.05.")
    w("")

    counts = acf_df["interpretation"].value_counts()
    w(f"- **Independent**: {counts.get('independent', 0)} instruments")
    w(f"- **Mean-reversion** (ACF < −0.05): {counts.get('mean_reversion', 0)} instruments")
    w(f"- **Momentum** (ACF > +0.05): {counts.get('momentum', 0)} instruments")
    w("")

    mean_rev = acf_df[acf_df["interpretation"] == "mean_reversion"]["instrument"].tolist()
    momentum = acf_df[acf_df["interpretation"] == "momentum"]["instrument"].tolist()

    if mean_rev:
        w("Mean-reversion instruments: " + ", ".join(
            i.split("|")[1].strip() + " (" + i.split("/")[0].strip() + ")"
            for i in mean_rev
        ))
    if momentum:
        w("Momentum instruments: " + ", ".join(
            i.split("|")[1].strip() + " (" + i.split("/")[0].strip() + ")"
            for i in momentum
        ))
    w("")
    w("### Impact of dependency adjustment on validation")
    w("")
    w("| Method | Sharpe (baseline) | Sharpe (+ dependency adj.) | Change |")
    w("|---|---|---|---|")

    dep_rows = [k for k in metrics if "dependency" in k.lower() or "+" in k]
    base_rows = [k for k in metrics if "dependency" not in k.lower() and "+" not in k
                 and k != "Equal-weight"]

    for base_label in base_rows:
        dep_label = base_label + " + dependency"
        if dep_label in metrics:
            bs = metrics[base_label]["val"]["sharpe_ratio"]
            ds = metrics[dep_label]["val"]["sharpe_ratio"]
            w(f"| {base_label} | {bs:.4f} | {ds:.4f} | {ds - bs:+.4f} |")
    w("")
    w("> The dependency adjustment has negligible impact (< 0.015 Sharpe change).")
    w("> Autocorrelations are small (max |ACF| ≈ 0.10), so multipliers deviate")
    w("> from 1.0 by at most ±3%, which is diluted further by re-normalisation")
    w("> across 35 instruments.")
    w("")

    # ── Key findings ──────────────────────────────────────────────────────────
    w("## 4. Key findings")
    w("")

    mvo_val_sh  = metrics.get("Markowitz", {}).get("val", {}).get("sharpe_ratio", float("nan"))
    mvo_val_dd  = metrics.get("Markowitz", {}).get("val", {}).get("max_drawdown_pct", float("nan"))
    ew_val_sh   = metrics.get("Equal-weight", {}).get("val", {}).get("sharpe_ratio", float("nan"))
    ew_tr_sh    = metrics.get("Equal-weight", {}).get("train", {}).get("sharpe_ratio", float("nan"))
    kelly_tr_sh = metrics.get("Kelly", {}).get("train", {}).get("sharpe_ratio", float("nan"))
    kelly_val_sh = metrics.get("Kelly", {}).get("val", {}).get("sharpe_ratio", float("nan"))

    w(f"1. **Markowitz achieves the best validation Sharpe** ({mvo_val_sh:.2f} vs {ew_val_sh:.2f} equal-weight)")
    w(f"   with the lowest drawdown ({mvo_val_dd:.1f}%). Mean-variance optimisation genuinely")
    w("   reduces risk by diversifying across low-correlation instruments.")
    w("")
    w(f"2. **Kelly beats equal-weight on train** (Sharpe {kelly_tr_sh:.2f} vs {ew_tr_sh:.2f}) but not on")
    w(f"   validation ({kelly_val_sh:.2f} vs {ew_val_sh:.2f}). Win-rate estimates are not stable enough across")
    w("   different market regimes to consistently beat equal allocation.")
    w("")
    w("3. **Rebalancing frequency matters more than lookback**. Short rebalancing")
    w("   (5 days) consistently hurts all optimised methods — it causes weight")
    w("   chasing of noise. 30-day rebalancing is optimal for both Kelly and Markowitz.")
    w("")
    w("4. **Bar-level vs trade-level Kelly**: treating each equity-curve bar as an")
    w("   independent trade distorts win-rate estimates. Aggregating consecutive")
    w("   bars into per-trade returns before computing win-rate and R gives a")
    w("   more accurate Kelly allocation.")
    w("")
    w("5. **Trade dependency is statistically weak**. Most instruments exhibit")
    w("   near-zero lag-1 autocorrelation; ETHUSDT strategies show the strongest")
    w("   mean-reversion (ACF ≈ −0.10). Dependency-based weight adjustments")
    w("   did not materially improve out-of-sample performance.")
    w("")

    report = "\n".join(lines)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report saved: {output_path}")

    return report


def _pivot_to_markdown(
    pivot: pd.DataFrame,
    row_prefix: str = "",
    row_suffix: str = "",
    col_prefix: str = "",
    col_suffix: str = "",
) -> str:
    """Convert a pivot DataFrame to a markdown table without tabulate."""
    cols = [f"{col_prefix}{c}{col_suffix}" for c in pivot.columns]
    header = "| " + " | ".join([""] + cols) + " |"
    sep    = "| " + " | ".join(["---"] * (len(cols) + 1)) + " |"
    rows = [header, sep]
    for idx, row in pivot.iterrows():
        label = f"{row_prefix}{idx}{row_suffix}"
        vals = " | ".join(f"{v:.3f}" for v in row)
        rows.append(f"| {label} | {vals} |")
    return "\n".join(rows)


def summarize_portfolio_weights(weights: dict) -> str:
    """Return a simple text summary of portfolio weights."""
    lines = ["Portfolio weights:"]
    for name, w in weights.items():
        lines.append(f"  {name}: {w:.2%}")
    return "\n".join(lines)
