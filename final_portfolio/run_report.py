"""Generate all final_portfolio figures and the markdown report in one run.

Usage:
    cd RR_Szatan_Lambert_Kowalczyk_Szostak
    python3 -m final_portfolio.run_report
"""

from __future__ import annotations

from pathlib import Path

from final_portfolio.equal_weight import DEFAULT_EQUITY_CURVES, run_equal_weight
from final_portfolio.kelly import run_kelly_portfolio, grid_search_kelly
from final_portfolio.markowitz import run_markowitz_portfolio, grid_search_markowitz
from final_portfolio.trade_dependency import (
    compute_trade_autocorrelations,
    run_kelly_with_dependency,
    run_markowitz_with_dependency,
)
from final_portfolio.portfolio_report import generate_report
from final_portfolio.visuals.equity_curves import (
    plot_method_comparison,
    plot_full_timeline,
    plot_equal_weight,
)
from final_portfolio.visuals.analysis_plots import (
    plot_grid_search_heatmaps,
    plot_acf_bars,
    plot_drawdown_comparison,
)

CSV  = DEFAULT_EQUITY_CURVES
FIGS = Path(__file__).resolve().parents[1] / "outputs" / "figures"
RPTS = Path(__file__).resolve().parents[1] / "outputs" / "report"


def main() -> None:
    # ── Step 1: grid searches (train only) ───────────────────────────────────
    print("Running Kelly grid search...")
    kelly_grid = grid_search_kelly(CSV)

    print("Running Markowitz grid search...")
    mvo_grid = grid_search_markowitz(CSV)

    # Best parameters selected automatically from grid search results
    best_kelly = kelly_grid.iloc[0]
    kelly_lb = int(best_kelly["lookback"])
    kelly_rb = int(best_kelly["rebalancing_days"])
    print(f"  Best Kelly params: lookback={kelly_lb} trades, rebalancing={kelly_rb} days")

    best_mvo = mvo_grid.iloc[0]
    mvo_lb = int(best_mvo["lookback_days"])
    mvo_rb = int(best_mvo["rebalancing_days"])
    print(f"  Best Markowitz params: lookback={mvo_lb} days, rebalancing={mvo_rb} days")

    # ── Step 2: equity curves — best params, both splits ─────────────────────
    print("Computing equity curves...")

    eq_t,  eq_tm  = run_equal_weight(CSV, split="train")
    eq_v,  eq_vm  = run_equal_weight(CSV, split="validation")

    kt, kelly_tm, _ = run_kelly_portfolio(CSV, kelly_lb, kelly_rb, split="train")
    kv, kelly_vm, _ = run_kelly_portfolio(CSV, kelly_lb, kelly_rb, split="validation")

    mt, mvo_tm, _ = run_markowitz_portfolio(CSV, mvo_lb, mvo_rb, split="train")
    mv, mvo_vm, _ = run_markowitz_portfolio(CSV, mvo_lb, mvo_rb, split="validation")

    # ── Step 3: dependency-adjusted curves (validation only) ─────────────────
    print("Computing dependency-adjusted curves...")
    _, kd_vm, _ = run_kelly_with_dependency(CSV, kelly_lb, kelly_rb, split="validation")
    _, md_vm, _ = run_markowitz_with_dependency(CSV, mvo_lb, mvo_rb, split="validation")

    # ── Step 4: trade dependency analysis ────────────────────────────────────
    print("Computing trade autocorrelations...")
    acf_df = compute_trade_autocorrelations(CSV, split="train")

    # ── Step 5: figures ───────────────────────────────────────────────────────
    print("Generating figures...")

    train_curves = {"Equal-weight": eq_t, "Kelly": kt, "Markowitz": mt}
    val_curves   = {"Equal-weight": eq_v, "Kelly": kv, "Markowitz": mv}
    train_metrics = {"Equal-weight": eq_tm, "Kelly": kelly_tm, "Markowitz": mvo_tm}
    val_metrics   = {"Equal-weight": eq_vm, "Kelly": kelly_vm, "Markowitz": mvo_vm}

    plot_method_comparison(
        train_curves, val_curves, train_metrics, val_metrics,
        output_path=FIGS / "final_portfolio_comparison.png",
    )
    plot_full_timeline(
        train_curves, val_curves,
        output_path=FIGS / "final_portfolio_timeline.png",
    )
    plot_equal_weight(
        csv_path=CSV, split="train",
        output_path=FIGS / "final_portfolio_equal_weight_train.png",
    )
    plot_grid_search_heatmaps(
        kelly_grid, mvo_grid,
        output_path=FIGS / "final_portfolio_grid_search.png",
    )
    plot_acf_bars(
        acf_df,
        output_path=FIGS / "final_portfolio_acf.png",
    )
    plot_drawdown_comparison(
        val_curves,
        output_path=FIGS / "final_portfolio_drawdowns_val.png",
    )

    # ── Step 6: report ────────────────────────────────────────────────────────
    print("Generating report...")

    all_metrics = {
        "Equal-weight":              {"train": eq_tm,    "val": eq_vm},
        "Kelly":                     {"train": kelly_tm, "val": kelly_vm},
        "Markowitz":                 {"train": mvo_tm,   "val": mvo_vm},
        "Kelly + dependency":        {"train": kelly_tm, "val": kd_vm},
        "Markowitz + dependency":    {"train": mvo_tm,   "val": md_vm},
    }

    report_text = generate_report(
        metrics=all_metrics,
        acf_df=acf_df,
        kelly_grid=kelly_grid,
        markowitz_grid=mvo_grid,
        output_path=RPTS / "final_portfolio_report.md",
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("DONE — files generated:")
    print(f"  Figures : {FIGS}")
    for f in sorted(FIGS.glob("final_portfolio_*.png")):
        print(f"    {f.name}")
    print(f"  Report  : {RPTS / 'final_portfolio_report.md'}")
    print("=" * 60)

    print("\n=== Quick results summary ===")
    print(f"{'Method':<28} {'Train Sh':>9} {'Val Sh':>8} {'Val Ret':>9} {'Val DD':>9}")
    print("-" * 60)
    for label, m in list(all_metrics.items())[:3]:
        t, v = m["train"], m["val"]
        print(f"{label:<28} {t['sharpe_ratio']:>9.3f} {v['sharpe_ratio']:>8.3f}"
              f" {v['total_return_pct']:>+8.1f}% {v['max_drawdown_pct']:>+8.1f}%")


if __name__ == "__main__":
    main()
