"""Export pre-split CSV files (train / validation / test) per asset.

Reads the unified CSVs produced by :mod:`preprocessing.export_unified`,
applies the global time boundaries from :class:`preprocessing.splitter.DataSplitter`,
and writes ready-to-load CSV files so that downstream code never needs
to run preprocessing at import time.

Output layout::

    data/processed/splits/csv/
        AAPL_equities_15min_train.csv
        AAPL_equities_15min_val.csv
        AAPL_equities_15min_test.csv
        ...

Example
-------
.. code-block:: bash

    python -m preprocessing.export_splits
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from .build_data_manifest import DATA_ROOT
from .export_unified import DEFAULT_OUTPUT_DIR as UNIFIED_DIR
from .export_unified import export_unified_csvs
from .splitter import DataSplitter

logger = logging.getLogger(__name__)

DEFAULT_SPLIT_CSV_DIR = DATA_ROOT / "processed" / "splits" / "csv"

_PARTITION_NAMES = ("train", "val", "test")


def export_split_csvs(
    unified_dir: Path = UNIFIED_DIR,
    output_dir: Path = DEFAULT_SPLIT_CSV_DIR,
    regenerate_unified: bool = False,
) -> list[Path]:
    """Split every unified CSV into train/val/test and write to disk.

    Parameters
    ----------
    unified_dir : Path
        Directory with unified CSVs (one per asset).
    output_dir : Path
        Where to write the split CSVs.
    regenerate_unified : bool
        If ``True``, re-export unified CSVs before splitting.

    Returns
    -------
    list[Path]
        All written CSV paths.
    """
    if regenerate_unified or not any(unified_dir.glob("*.csv")):
        logger.info("Generating unified CSVs first...")
        export_unified_csvs(output_dir=unified_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    splitter = DataSplitter()
    written: list[Path] = []

    for csv_path in sorted(unified_dir.glob("*.csv")):
        df = pd.read_csv(csv_path)
        stem = csv_path.stem  # e.g. AAPL_equities_15min

        result = splitter.split(df)

        for partition_name, partition_df in zip(
            _PARTITION_NAMES,
            [result.train, result.validation, result.test],
        ):
            out_path = output_dir / f"{stem}_{partition_name}.csv"
            partition_df.to_csv(out_path, index=False)
            written.append(out_path)
            logger.info("  %s — %d rows", out_path.name, len(partition_df))

    logger.info("Wrote %d split CSVs to %s", len(written), output_dir)
    return written


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for split CSV export."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Export pre-split CSVs per asset.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_SPLIT_CSV_DIR),
        help="Directory for split output CSVs.",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Re-export unified CSVs before splitting.",
    )
    args = parser.parse_args(argv)
    paths = export_split_csvs(
        output_dir=Path(args.output_dir),
        regenerate_unified=args.regenerate,
    )
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
