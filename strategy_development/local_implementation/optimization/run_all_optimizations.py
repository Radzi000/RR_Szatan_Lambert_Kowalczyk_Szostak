"""Aggregate runner for all Workstream C optimization pipelines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .common import (
    TABLE_FILENAMES,
    add_common_args,
    build_cost_config_from_args,
    default_strategy_configs,
    load_optimization_splits,
    parse_asset_list,
    run_backtest_for_params_with_costs,
    run_strategy_optimization,
)
from .io import ensure_output_dirs, write_convergence_plot, write_csv, write_train_validation_plot
from .metrics import compute_metric_bundle


def _curve_detail_frame(
    result,
    *,
    strategy: str,
    optimizer: str,
    asset: str,
    asset_class: str,
    frequency: str,
    split: str,
    params_json: str,
    selected_by: str,
    cost_bps: float,
) -> pd.DataFrame:
    detail = result.equity_detail.copy()
    if detail.empty:
        return pd.DataFrame()
    detail["timestamp"] = pd.to_datetime(detail["timestamp"], utc=True)
    detail = detail.reset_index(drop=True)
    detail["bar_index"] = detail.index.astype(int)
    peak = detail["net_equity"].cummax()
    detail["drawdown"] = ((detail["net_equity"] / peak) - 1.0) * 100.0
    detail["strategy"] = strategy
    detail["config_source"] = "optimized"
    detail["optimizer"] = optimizer
    detail["asset"] = asset
    detail["asset_class"] = asset_class
    detail["frequency"] = frequency
    detail["split"] = split
    detail["cost_bps"] = float(cost_bps)
    detail["params_json"] = params_json
    detail["selected_by"] = selected_by
    return detail[
        [
            "bar_index",
            "timestamp",
            "strategy",
            "config_source",
            "optimizer",
            "asset",
            "asset_class",
            "frequency",
            "split",
            "gross_equity",
            "net_equity",
            "net_return_pct",
            "drawdown",
            "turnover",
            "transaction_cost",
            "cumulative_transaction_cost",
            "cost_bps",
            "params_json",
            "selected_by",
        ]
    ].rename(columns={"net_return_pct": "net_return"})


def _sanitize_curve_frame(frame: pd.DataFrame, *, label: str) -> pd.DataFrame:
    cleaned = frame.copy()
    cleaned["timestamp"] = pd.to_datetime(cleaned["timestamp"], utc=True)
    key_cols = ["bar_index", "strategy", "asset", "asset_class", "split"]
    if cleaned.duplicated(subset=key_cols).any():
        raise ValueError(f"{label} contains duplicate bar_index/strategy/asset/split rows.")
    numeric_cols = [
        col
        for col in cleaned.columns
        if col.endswith("_equity")
        or col.endswith("_return")
        or col == "drawdown"
        or col.endswith("_cost")
    ]
    for col in numeric_cols:
        if cleaned[col].isna().any() or not np.isfinite(cleaned[col]).all():
            raise ValueError(f"{label} contains NaN/inf values in {col}.")
    if "net_equity" in cleaned.columns:
        starts = cleaned.sort_values("bar_index").groupby(
            ["strategy", "asset", "split"], as_index=False
        ).first()
        if ((starts["net_equity"] < 95_000) | (starts["net_equity"] > 100_000)).any():
            raise ValueError(f"{label} has unexpected starting equity levels.")
    if "drawdown" in cleaned.columns and (cleaned["drawdown"] > 1e-9).any():
        raise ValueError(f"{label} contains positive drawdowns.")
    return cleaned.sort_values(["split", "asset_class", "strategy", "asset", "bar_index"]).reset_index(
        drop=True
    )


def _aggregate_curve_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby(["split", "asset_class", "strategy", "bar_index"], as_index=False)
        .agg(
            median_net_equity=("net_equity", "median"),
            median_net_return=("net_return", "median"),
            median_drawdown=("drawdown", "median"),
            curve_count=("asset", "nunique"),
            representative_timestamp=("timestamp", "max"),
        )
        .sort_values(["split", "asset_class", "strategy", "bar_index"])
        .reset_index(drop=True)
    )


def _plot_split_panels(
    aggregated: pd.DataFrame,
    *,
    split: str,
    value_col: str,
    ylabel: str,
    title: str,
    output_path: Path,
) -> Path:
    split_frame = aggregated[aggregated["split"] == split].copy()
    asset_classes = ["equities", "commodities", "crypto"]
    fig, axes = plt.subplots(1, len(asset_classes), figsize=(18, 5), sharey=True)
    palette = plt.get_cmap("tab10")

    for idx, asset_class in enumerate(asset_classes):
        ax = axes[idx]
        chunk = split_frame[split_frame["asset_class"] == asset_class]
        if chunk.empty:
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
            ax.set_title(asset_class.title())
            ax.grid(True, linestyle="--", alpha=0.3)
            continue
        for color_idx, (strategy, strategy_chunk) in enumerate(chunk.groupby("strategy")):
            ax.plot(
                strategy_chunk["bar_index"],
                strategy_chunk[value_col],
                linewidth=1.3,
                color=palette(color_idx),
                label=strategy,
            )
        ax.set_title(asset_class.title())
        ax.grid(True, linestyle="--", alpha=0.3)
        if idx == 0:
            ax.set_ylabel(ylabel)
        ax.set_xlabel("Bar Index")
        ax.legend(fontsize=7)

    fig.suptitle(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def _write_our_strategy_artifacts(
    *,
    selected_params: pd.DataFrame,
    output_dir: Path,
    cost_config,
) -> list[Path]:
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    config_by_label = {config.spec.label: config for config in default_strategy_configs()}

    curve_rows: list[dict[str, object]] = []
    verification_rows: list[dict[str, object]] = []

    for row in selected_params.itertuples(index=False):
        config = config_by_label[row.strategy]
        params = json.loads(row.params_json)
        split_data = load_optimization_splits(row.asset, row.asset_class)

        for split_name in ["train", "validation"]:
            daily_data, minute_data = split_data[split_name]
            result, _ = run_backtest_for_params_with_costs(
                config.spec.factory,
                params,
                daily_data,
                minute_data,
                asset_class=row.asset_class,
                cost_config=cost_config,
            )
            metrics = compute_metric_bundle(result, minute_data)
            detail_frame = _curve_detail_frame(
                result,
                strategy=row.strategy,
                optimizer=row.optimizer,
                asset=row.asset,
                asset_class=row.asset_class,
                frequency=row.frequency,
                split=split_name,
                params_json=row.params_json,
                selected_by=row.selected_by,
                cost_bps=float(row.cost_bps),
            )
            if not detail_frame.empty:
                curve_rows.extend(detail_frame.to_dict("records"))

            verification_rows.append(
                {
                    "strategy": row.strategy,
                    "config_source": "optimized",
                    "optimizer": row.optimizer,
                    "asset": row.asset,
                    "asset_class": row.asset_class,
                    "frequency": row.frequency,
                    "split": split_name,
                    "cost_bps": round(float(row.cost_bps), 6),
                    "gross_total_return": round(float(metrics.gross_total_return), 6),
                    "net_total_return": round(float(metrics.net_total_return), 6),
                    "annualized_return": round(float(metrics.annualized_return), 6),
                    "annualized_volatility": round(float(metrics.annualized_volatility), 6),
                    "net_sharpe": round(float(metrics.net_sharpe), 6),
                    "sortino": round(float(metrics.sortino), 6),
                    "max_drawdown": round(float(metrics.max_drawdown), 6),
                    "calmar": round(float(metrics.calmar), 6),
                    "hit_rate": round(float(metrics.hit_rate), 6),
                    "turnover": round(float(metrics.turnover), 6),
                    "total_transaction_cost": round(float(metrics.total_transaction_cost), 6),
                    "trade_count": int(metrics.trade_count),
                    "average_trade_pnl": round(float(metrics.average_trade_pnl), 6),
                    "exposure_time": round(float(metrics.exposure_time), 6),
                    "params_json": row.params_json,
                    "selected_by": row.selected_by,
                }
            )

    curve_df = _sanitize_curve_frame(pd.DataFrame(curve_rows), label="our strategy chart data")
    aggregated_df = _aggregate_curve_frame(curve_df)
    verification_df = pd.DataFrame(verification_rows)

    equity_path = tables_dir / "equity_curves_our_strats.csv"
    drawdown_path = tables_dir / "drawdowns_our_strats.csv"
    verification_path = tables_dir / "verification_metrics_our_strats.csv"
    aggregate_path = tables_dir / "equity_drawdown_our_strats_aggregated.csv"
    write_csv(equity_path, curve_df)
    write_csv(drawdown_path, curve_df)
    write_csv(aggregate_path, aggregated_df)
    write_csv(verification_path, verification_df)

    equity_png = figures_dir / "equity_curves_our_strats.png"
    drawdown_png = figures_dir / "drawdowns_our_strats.png"
    train_equity_png = figures_dir / "equity_curves_our_strats_train.png"
    validation_equity_png = figures_dir / "equity_curves_our_strats_validation.png"
    train_drawdown_png = figures_dir / "drawdowns_our_strats_train.png"
    validation_drawdown_png = figures_dir / "drawdowns_our_strats_validation.png"

    _plot_split_panels(
        aggregated_df,
        split="train",
        value_col="median_net_equity",
        ylabel="Median Net Equity",
        title="Our Trained Strategies Train Equity Curves",
        output_path=train_equity_png,
    )
    _plot_split_panels(
        aggregated_df,
        split="validation",
        value_col="median_net_equity",
        ylabel="Median Net Equity",
        title="Our Trained Strategies Validation Equity Curves",
        output_path=validation_equity_png,
    )
    _plot_split_panels(
        aggregated_df,
        split="train",
        value_col="median_drawdown",
        ylabel="Median Drawdown (%)",
        title="Our Trained Strategies Train Drawdowns",
        output_path=train_drawdown_png,
    )
    _plot_split_panels(
        aggregated_df,
        split="validation",
        value_col="median_drawdown",
        ylabel="Median Drawdown (%)",
        title="Our Trained Strategies Validation Drawdowns",
        output_path=validation_drawdown_png,
    )

    # Compatibility aliases: point the legacy names to the validation view,
    # which is the relevant post-selection chart for Workstream C.
    validation_equity_img = plt.imread(validation_equity_png)
    plt.imsave(equity_png, validation_equity_img)
    validation_drawdown_img = plt.imread(validation_drawdown_png)
    plt.imsave(drawdown_png, validation_drawdown_img)

    return [
        equity_path,
        drawdown_path,
        aggregate_path,
        verification_path,
        equity_png,
        drawdown_png,
        train_equity_png,
        validation_equity_png,
        train_drawdown_png,
        validation_drawdown_png,
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all Workstream C optimization pipelines.")
    add_common_args(parser)
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    tables_dir, figures_dir = ensure_output_dirs(output_dir)
    cost_config = build_cost_config_from_args(args)

    aggregated: dict[str, list[pd.DataFrame]] = {
        "search_results": [],
        "selected_params": [],
        "comparison": [],
        "verification": [],
    }

    for config in default_strategy_configs():
        result_frames = run_strategy_optimization(
            config,
            max_iters=args.max_iters,
            population=args.population,
            seed=args.seed,
            smoke=args.smoke,
            output_dir=output_dir,
            assets=parse_asset_list(args.assets),
            cost_config=cost_config,
        )
        for key, frame in result_frames.items():
            aggregated[key].append(frame)

    combined = {
        key: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        for key, frames in aggregated.items()
    }

    search_path = write_csv(tables_dir / TABLE_FILENAMES["search_results"], combined["search_results"])
    selected_path = write_csv(tables_dir / TABLE_FILENAMES["selected_params"], combined["selected_params"])
    comparison_path = write_csv(tables_dir / TABLE_FILENAMES["comparison"], combined["comparison"])
    verification_path = write_csv(tables_dir / TABLE_FILENAMES["verification"], combined["verification"])
    convergence_path = write_convergence_plot(
        combined["search_results"],
        figures_dir / "optimization_convergence.png",
    )
    comparison_fig_path = write_train_validation_plot(
        combined["comparison"],
        figures_dir / "train_validation_sharpe_comparison.png",
    )

    extra_paths = _write_our_strategy_artifacts(
        selected_params=combined["selected_params"],
        output_dir=output_dir,
        cost_config=cost_config,
    )

    for path in [
        search_path,
        selected_path,
        comparison_path,
        verification_path,
        convergence_path,
        comparison_fig_path,
        *extra_paths,
    ]:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
