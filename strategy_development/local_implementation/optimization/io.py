"""I/O helpers for Workstream C outputs."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def ensure_output_dirs(output_dir: Path) -> tuple[Path, Path]:
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    return tables_dir, figures_dir


def params_to_json(params: dict[str, int | float]) -> str:
    return json.dumps(params, sort_keys=True)


def write_csv(path: Path, frame: pd.DataFrame) -> Path:
    frame.to_csv(path, index=False)
    return path


def write_convergence_plot(search_results: pd.DataFrame, output_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6))
    if not search_results.empty:
        grouped = (
            search_results.sort_values("iteration")
            .groupby(["strategy", "optimizer", "iteration"], as_index=False)["train_net_sharpe"]
            .max()
        )
        grouped["best_so_far"] = grouped.groupby(["strategy", "optimizer"])["train_net_sharpe"].cummax()
        for (strategy, optimizer), chunk in grouped.groupby(["strategy", "optimizer"]):
            ax.plot(
                chunk["iteration"],
                chunk["best_so_far"],
                label=f"{strategy} [{optimizer}]",
                linewidth=1.5,
            )
    ax.set_title("Optimization Convergence")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Best-So-Far Train Net Sharpe")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def write_train_validation_plot(comparison: pd.DataFrame, output_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6))
    if not comparison.empty:
        plot_frame = (
            comparison.groupby(["strategy", "optimizer"], as_index=False)[
                ["baseline_validation_net_sharpe", "optimized_validation_net_sharpe"]
            ]
            .mean()
        )
        x = range(len(plot_frame))
        ax.bar(
            [value - 0.2 for value in x],
            plot_frame["baseline_validation_net_sharpe"],
            width=0.4,
            label="Baseline validation net Sharpe",
        )
        ax.bar(
            [value + 0.2 for value in x],
            plot_frame["optimized_validation_net_sharpe"],
            width=0.4,
            label="Optimized validation net Sharpe",
        )
        ax.set_xticks(list(x))
        ax.set_xticklabels(
            [f"{row.strategy}\n[{row.optimizer}]" for row in plot_frame.itertuples()],
            rotation=20,
            ha="right",
        )
    ax.set_title("Train/Validation Net Sharpe Comparison")
    ax.set_ylabel("Validation Net Sharpe")
    ax.grid(True, linestyle="--", axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
