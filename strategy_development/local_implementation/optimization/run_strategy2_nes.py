"""Run NES optimization for the second local strategy (Strategy1)."""

from __future__ import annotations

import argparse
from pathlib import Path

from .common import TABLE_FILENAMES, add_common_args, default_strategy_configs, parse_asset_list, run_strategy_optimization
from .io import ensure_output_dirs, write_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run NES optimization for Strategy1 / second strategy.")
    add_common_args(parser)
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir) / "optimization" / "strategy2_nes"
    tables_dir, _ = ensure_output_dirs(output_dir)
    results = run_strategy_optimization(
        default_strategy_configs()[1],
        max_iters=args.max_iters,
        population=args.population,
        seed=args.seed,
        smoke=args.smoke,
        output_dir=output_dir,
        assets=parse_asset_list(args.assets),
    )
    for key, frame in results.items():
        write_csv(tables_dir / TABLE_FILENAMES[key], frame)
        print(tables_dir / TABLE_FILENAMES[key])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
