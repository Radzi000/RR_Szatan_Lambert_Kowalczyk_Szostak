"""Build deterministic global train/validation/test split boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .build_data_manifest import DATA_ROOT, discover_assets, load_raw_csv
from .validate_schema import normalize_ohlcv_frame

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = DATA_ROOT / "processed" / "splits"


def build_global_split_manifest(
    data_root: Path = DATA_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    frequency: str = "15min",
) -> Path:
    """Build deterministic global split boundaries across committed assets."""
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = [asset for asset in discover_assets(data_root=data_root) if asset.frequency == frequency]
    if not assets:
        raise ValueError(f"No assets found for frequency {frequency}")

    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    asset_summaries: list[dict[str, str]] = []
    for asset in assets:
        raw = load_raw_csv(asset.path)
        normalized = normalize_ohlcv_frame(raw, asset)
        start = pd.Timestamp(normalized["timestamp"].iloc[0])
        end = pd.Timestamp(normalized["timestamp"].iloc[-1])
        windows.append((start, end))
        asset_summaries.append(
            {
                "asset": asset.asset,
                "asset_class": asset.asset_class,
                "start": str(start),
                "end": str(end),
            }
        )

    global_start = max(start for start, _ in windows)
    global_end = min(end for _, end in windows)
    if global_start >= global_end:
        raise ValueError("No overlapping global time window across assets")

    timeline = pd.date_range(start=global_start, end=global_end, freq="15min")
    if len(timeline) < 3:
        raise ValueError("Insufficient overlapping timestamps to create deterministic splits")

    train_end_idx = int(len(timeline) * 0.70) - 1
    validation_end_idx = int(len(timeline) * 0.85) - 1
    train_end_idx = max(train_end_idx, 0)
    validation_end_idx = max(validation_end_idx, train_end_idx + 1)

    split_manifest = {
        "frequency": frequency,
        "global_window": {
            "start": str(global_start),
            "end": str(global_end),
            "timestamp_count": len(timeline),
        },
        "split_boundaries": {
            "train": {
                "start": str(timeline[0]),
                "end": str(timeline[train_end_idx]),
            },
            "validation": {
                "start": str(timeline[train_end_idx + 1]),
                "end": str(timeline[validation_end_idx]),
            },
            "test": {
                "start": str(timeline[validation_end_idx + 1]),
                "end": str(timeline[-1]),
            },
        },
        "assets": asset_summaries,
    }

    split_path = output_dir / "global_time_splits.json"
    split_path.write_text(json.dumps(split_manifest, indent=2), encoding="utf-8")
    return split_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deterministic global split generation."""
    parser = argparse.ArgumentParser(description="Build deterministic global train/validation/test split boundaries.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the split manifest JSON should be written.",
    )
    parser.add_argument(
        "--frequency",
        default="15min",
        help="Frequency group to split. Defaults to 15min.",
    )
    args = parser.parse_args(argv)
    split_path = build_global_split_manifest(output_dir=Path(args.output_dir), frequency=args.frequency)
    print(split_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
