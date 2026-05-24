"""Export unified, preprocessed CSV files from committed raw data.

Reads every raw asset discovered by the manifest builder, normalizes
it to the shared OHLCV schema, and writes one CSV per asset into
``data/processed/unified/``.  The result is a set of clean,
timezone-aware, sorted CSV files ready for strategy consumption.

Example
-------
.. code-block:: bash

    python -m preprocessing.export_unified
    python -m preprocessing.export_unified --output-dir data/processed/unified
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from .build_data_manifest import DATA_ROOT, PROJECT_ROOT, discover_assets, load_raw_csv
from .validate_schema import normalize_ohlcv_frame, validate_ohlcv_schema

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = DATA_ROOT / "processed" / "unified"


def export_unified_csvs(
    data_root: Path = DATA_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    """Normalize and export all raw assets as unified CSVs.

    Each output file has columns:
    ``timestamp, open, high, low, close, volume, asset, asset_class,
    frequency, source_file``.  Timestamps are UTC-aware and the rows
    are sorted chronologically.

    Parameters
    ----------
    data_root : Path
        Root directory containing raw data sub-folders.
    output_dir : Path
        Where to write the unified CSVs.

    Returns
    -------
    list[Path]
        Paths to the written CSV files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = discover_assets(data_root=data_root)
    written: list[Path] = []

    for asset in assets:
        raw = load_raw_csv(asset.path)
        normalized = normalize_ohlcv_frame(raw, asset)
        validate_ohlcv_schema(normalized)

        # Ensure chronological order
        normalized = normalized.sort_values("timestamp").reset_index(drop=True)

        filename = f"{asset.asset}_{asset.asset_class}_{asset.frequency}.csv"
        out_path = output_dir / filename
        normalized.to_csv(out_path, index=False)
        written.append(out_path)
        logger.info(
            "Exported %s — %d rows (%s → %s)",
            filename,
            len(normalized),
            normalized["timestamp"].iloc[0],
            normalized["timestamp"].iloc[-1],
        )

    logger.info("Exported %d unified CSVs to %s", len(written), output_dir)
    return written


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for unified CSV export."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Export unified, preprocessed CSVs.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for unified output CSVs.",
    )
    args = parser.parse_args(argv)
    paths = export_unified_csvs(output_dir=Path(args.output_dir))
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
