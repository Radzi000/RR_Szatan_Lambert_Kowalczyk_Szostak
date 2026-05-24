"""Deterministic end-to-end reproduction entry point."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .backtest.engine import BacktestEngine, BacktestResult
from .data.provider import DataProvider
from .strategies import Strategy0, Strategy1, Strategy2, Strategy3, Strategy4
from .visualization.plots import plot_strategy_comparison

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
DATA_ROOT = PROJECT_ROOT / "data"


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_versions() -> dict[str, str]:
    packages = ["intraday-momentum", "numpy", "pandas", "matplotlib", "seaborn", "yfinance"]
    versions: dict[str, str] = {}
    for package_name in packages:
        try:
            versions[package_name] = metadata.version(package_name)
        except metadata.PackageNotFoundError:
            versions[package_name] = "not-installed"
    return versions


def _display_path(path: Path, base: Path = PROJECT_ROOT) -> str:
    """Render a relative path when possible, otherwise fall back to absolute."""
    try:
        rendered = path.relative_to(base)
    except ValueError:
        rendered = path.resolve()
    return str(rendered).replace("\\", "/")


def _git_commit_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _clean_output_dir(output_dir: Path) -> None:
    for relative_dir in ["tables", "figures", "report"]:
        target_dir = output_dir / relative_dir
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)


def _load_reproduction_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    provider = DataProvider(ticker="SPY", data_dir=DATA_ROOT, allow_download=False)
    minute_data = provider.get_data("1900-01-01", "2100-01-01", interval="5m", use_cache=False)
    minute_start = minute_data.index.min().date().isoformat()
    minute_end = minute_data.index.max().date().isoformat()
    daily_start = (pd.Timestamp(minute_start) - pd.Timedelta(days=60)).date().isoformat()
    daily_data = provider.get_daily_data(daily_start, minute_end)
    return daily_data, minute_data


def _run_strategies(daily_data: pd.DataFrame, minute_data: pd.DataFrame) -> dict[str, BacktestResult]:
    engine = BacktestEngine(initial_capital=100_000.0, commission_per_share=0.005)
    results: dict[str, BacktestResult] = {}
    for spec in STRATEGY_SPECS:
        strategy = spec.factory(**spec.params)
        results[spec.label] = engine.run(strategy, daily_data, minute_data)
    return results


def _summary_frame(results: dict[str, BacktestResult]) -> pd.DataFrame:
    rows = []
    for spec in STRATEGY_SPECS:
        result = results[spec.label]
        summary = result.summary()
        rows.append(
            {
                "strategy": spec.label,
                "final_equity": round(summary["final_equity"], 2),
                "total_return_pct": round(summary["total_return_pct"], 4),
                "sharpe_ratio": round(summary["sharpe_ratio"], 4),
                "max_drawdown_pct": round(summary["max_drawdown_pct"], 4),
                "num_trades": int(summary["num_trades"]),
                "win_rate": round(summary["win_rate"], 4),
                "avg_win_pct": round(summary["avg_win_pct"], 4),
                "avg_loss_pct": round(summary["avg_loss_pct"], 4),
            }
        )
    return pd.DataFrame(rows)


def _write_summary_tables(summary_df: pd.DataFrame, output_dir: Path) -> list[Path]:
    tables_dir = output_dir / "tables"
    csv_path = tables_dir / "strategy_summary.csv"
    md_path = tables_dir / "strategy_summary.md"
    summary_df.to_csv(csv_path, index=False)
    md_path.write_text(summary_df.to_markdown(index=False) + "\n", encoding="utf-8")
    return [csv_path, md_path]


def _plot_drawdowns(results: dict[str, BacktestResult], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    palette = plt.get_cmap("tab10")
    for idx, spec in enumerate(STRATEGY_SPECS):
        curve = results[spec.label].equity_curve
        peak = curve.cummax()
        drawdown = (curve / peak - 1.0) * 100.0
        ax.plot(drawdown.index, drawdown.values, label=spec.label, linewidth=1.2, color=palette(idx))
    ax.set_title("Strategy Drawdowns", fontsize=13, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(fontsize=9, loc="lower left")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _write_figures(results: dict[str, BacktestResult], output_dir: Path) -> list[Path]:
    figures_dir = output_dir / "figures"
    equity_path = figures_dir / "equity_curves.png"
    drawdown_path = figures_dir / "drawdowns.png"

    equity_fig = plot_strategy_comparison(results, title="Intraday Momentum Strategy Comparison")
    equity_fig.savefig(equity_path, dpi=150)
    plt.close(equity_fig)

    _plot_drawdowns(results, drawdown_path)
    return [equity_path, drawdown_path]


def _write_report(
    summary_df: pd.DataFrame,
    daily_data: pd.DataFrame,
    minute_data: pd.DataFrame,
    output_dir: Path,
) -> Path:
    report_path = output_dir / "report" / "final_report.md"
    best_row = summary_df.sort_values("total_return_pct", ascending=False).iloc[0]
    report_lines = [
        "# Final Reproduction Report",
        "",
        "This report was generated by `python -m intraday_momentum.reproduce`.",
        "",
        "## Dataset",
        "",
        f"- Daily file: `data/1day/spy_daily.csv` ({daily_data.index.min().date()} to {daily_data.index.max().date()})",
        f"- Intraday file: `data/5min/spy_5m.csv` ({minute_data.index.min()} to {minute_data.index.max()})",
        "",
        "## Main Result",
        "",
        f"- Best total return: `{best_row['strategy']}` at `{best_row['total_return_pct']:.4f}%`.",
        f"- Strategies evaluated: `{len(summary_df)}`.",
        "",
        "## Generated Artifacts",
        "",
        "- `outputs/tables/strategy_summary.csv`",
        "- `outputs/tables/strategy_summary.md`",
        "- `outputs/tables/reproducibility_manifest.json`",
        "- `outputs/figures/equity_curves.png`",
        "- `outputs/figures/drawdowns.png`",
        "",
        "## Notes",
        "",
        "- The pipeline uses committed repository data only.",
        "- No notebooks are required for this workflow.",
        "- No live downloads are attempted in reproduce mode.",
        "",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return report_path


def _write_manifest(
    output_dir: Path,
    daily_data: pd.DataFrame,
    minute_data: pd.DataFrame,
    outputs: list[Path],
) -> Path:
    daily_file = DATA_ROOT / "1day" / "spy_daily.csv"
    minute_file = DATA_ROOT / "5min" / "spy_5m.csv"
    manifest_path = output_dir / "tables" / "reproducibility_manifest.json"
    manifest = {
        "python_version": sys.version.split()[0],
        "package_versions": _package_versions(),
        "git_commit_hash": _git_commit_hash(),
        "run_command": "python -m intraday_momentum.reproduce",
        "data_files": [
            {
                "path": _display_path(daily_file),
                "rows": len(daily_data),
                "date_range": [str(daily_data.index.min().date()), str(daily_data.index.max().date())],
                "sha256": _sha256(daily_file),
            },
            {
                "path": _display_path(minute_file),
                "rows": len(minute_data),
                "date_range": [str(minute_data.index.min()), str(minute_data.index.max())],
                "sha256": _sha256(minute_file),
            },
        ],
        "strategy_names": [spec.label for spec in STRATEGY_SPECS],
        "generated_outputs": [
            _display_path(path)
            for path in sorted([*outputs, manifest_path], key=lambda item: str(item))
        ],
        "environment": {
            "cwd": str(PROJECT_ROOT),
            "docker_offline_runtime_ready": True,
            "internet_required_at_runtime": False,
            "seed": 0,
            "matplotlib_backend": matplotlib.get_backend(),
            "timezone": os.environ.get("TZ", "not-set"),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def run_reproduction(output_dir: Path = DEFAULT_OUTPUT_DIR, generate_report: bool = True) -> dict[str, Path]:
    """Run the full deterministic research workflow and write stable outputs."""
    random.seed(0)
    np.random.seed(0)

    output_dir = Path(output_dir)
    _clean_output_dir(output_dir)

    daily_data, minute_data = _load_reproduction_data()
    results = _run_strategies(daily_data, minute_data)
    summary_df = _summary_frame(results)

    output_paths: list[Path] = []
    output_paths.extend(_write_summary_tables(summary_df, output_dir))
    output_paths.extend(_write_figures(results, output_dir))
    if generate_report:
        output_paths.append(_write_report(summary_df, daily_data, minute_data, output_dir))
    output_paths.append(_write_manifest(output_dir, daily_data, minute_data, output_paths))

    return {path.name: path for path in output_paths}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for reproducible research generation."""
    parser = argparse.ArgumentParser(description="Run the deterministic intraday momentum pipeline.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where tables, figures, and reports will be written.",
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Skip generation of outputs/report/final_report.md.",
    )
    args = parser.parse_args(argv)

    output_paths = run_reproduction(
        output_dir=Path(args.output_dir),
        generate_report=not args.skip_report,
    )
    for name, path in sorted(output_paths.items()):
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
