"""Run CMA-ES optimization for the fifth local strategy (Strategy4)."""

from __future__ import annotations

import argparse
from pathlib import Path

from .common import (
    TABLE_FILENAMES,
    add_common_args,
    build_cost_config_from_args,
    default_strategy_configs,
    parse_asset_list,
    run_strategy_optimization,
    runtime_settings_from_args,
)
from .io import ensure_output_dirs, write_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CMA-ES optimization for Strategy4 / fifth strategy.")
    add_common_args(parser)
    args = parser.parse_args(argv)
    settings = runtime_settings_from_args(args)
    output_dir = Path(args.output_dir) / "optimization" / "strategy5_cmaes"
    tables_dir, _ = ensure_output_dirs(output_dir)
    results = run_strategy_optimization(
        default_strategy_configs()[4],
        max_iters=settings.max_iters,
        population=settings.population,
        seed=args.seed,
        smoke=settings.smoke,
        output_dir=output_dir,
        assets=parse_asset_list(args.assets),
        cost_config=build_cost_config_from_args(args),
        asset_sample=settings.asset_sample,
        max_assets=settings.max_assets,
        timeout_minutes=settings.timeout_minutes,
        validation_candidates=settings.validation_candidates,
    )
    for key, frame in results.items():
        if key not in TABLE_FILENAMES:
            continue
        write_csv(tables_dir / TABLE_FILENAMES[key], frame)
        print(tables_dir / TABLE_FILENAMES[key])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
