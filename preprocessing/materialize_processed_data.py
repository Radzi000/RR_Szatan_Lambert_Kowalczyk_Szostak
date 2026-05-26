"""Materialize deterministic processed-data artifacts for downstream use."""

from __future__ import annotations

import argparse
from pathlib import Path

from .build_data_manifest import DATA_ROOT, DEFAULT_OUTPUT_DIR as MANIFEST_DIR
from .build_data_manifest import build_data_manifest
from .export_splits import DEFAULT_SPLIT_CSV_DIR, export_split_csvs
from .export_unified import DEFAULT_OUTPUT_DIR as UNIFIED_DIR
from .export_unified import export_unified_csvs
from .make_global_splits import DEFAULT_OUTPUT_DIR as SPLIT_DIR
from .make_global_splits import build_global_split_manifest


def materialize_processed_data(
    *,
    manifest_dir: Path = MANIFEST_DIR,
    split_dir: Path = SPLIT_DIR,
    unified_dir: Path = UNIFIED_DIR,
    split_csv_dir: Path = DEFAULT_SPLIT_CSV_DIR,
) -> dict[str, Path | list[Path]]:
    """Build the full deterministic preprocessing handoff contract.

    Returns a dictionary containing the manifest path, split manifest path,
    unified CSV paths, and split CSV paths.
    """
    manifest_path = build_data_manifest(output_dir=manifest_dir)
    split_manifest_path = build_global_split_manifest(output_dir=split_dir)
    unified_paths = export_unified_csvs(output_dir=unified_dir)
    split_csv_paths = export_split_csvs(
        unified_dir=unified_dir,
        output_dir=split_csv_dir,
        regenerate_unified=False,
    )
    return {
        "manifest_path": manifest_path,
        "split_manifest_path": split_manifest_path,
        "unified_paths": unified_paths,
        "split_csv_paths": split_csv_paths,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for materializing processed data artifacts."""
    parser = argparse.ArgumentParser(
        description="Materialize deterministic manifests, unified CSVs, and split CSVs.",
    )
    parser.parse_args(argv)
    outputs = materialize_processed_data()
    print(outputs["manifest_path"])
    print(outputs["split_manifest_path"])
    print(f"unified_csvs={len(outputs['unified_paths'])}")
    print(f"split_csvs={len(outputs['split_csv_paths'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
