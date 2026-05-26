"""Aggregate runner for all Workstream C optimization pipelines."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .common import (
    TABLE_FILENAMES,
    add_common_args,
    default_strategy_configs,
    parse_asset_list,
    run_strategy_optimization,
)
from .io import ensure_output_dirs, write_convergence_plot, write_csv, write_train_validation_plot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all Workstream C optimization pipelines.")
    add_common_args(parser)
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    tables_dir, figures_dir = ensure_output_dirs(output_dir)

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
        )
        for key, frame in result_frames.items():
            aggregated[key].append(frame)

    combined = {key: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame() for key, frames in aggregated.items()}

    write_csv(tables_dir / TABLE_FILENAMES["search_results"], combined["search_results"])
    write_csv(tables_dir / TABLE_FILENAMES["selected_params"], combined["selected_params"])
    write_csv(tables_dir / TABLE_FILENAMES["comparison"], combined["comparison"])
    write_csv(tables_dir / TABLE_FILENAMES["verification"], combined["verification"])
    write_convergence_plot(
        combined["search_results"],
        figures_dir / "optimization_convergence.png",
    )
    write_train_validation_plot(
        combined["comparison"],
        figures_dir / "train_validation_sharpe_comparison.png",
    )

    for path in [
        tables_dir / TABLE_FILENAMES["search_results"],
        tables_dir / TABLE_FILENAMES["selected_params"],
        tables_dir / TABLE_FILENAMES["comparison"],
        tables_dir / TABLE_FILENAMES["verification"],
        figures_dir / "optimization_convergence.png",
        figures_dir / "train_validation_sharpe_comparison.png",
    ]:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
