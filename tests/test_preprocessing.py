from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from preprocessing import build_global_split_manifest, discover_data_files, export_unified_csvs as build_unified_csvs
from preprocessing.build_data_manifest import build_data_manifest
from preprocessing.build_data_manifest import DATA_ROOT, discover_assets, load_raw_csv
from preprocessing.splitter import DataSplitter
from preprocessing.validate_schema import normalize_ohlcv_frame, validate_ohlcv_schema


def test_preprocessing_package_imports() -> None:
    assets = discover_data_files()
    assert assets


def test_15m_data_files_are_discoverable() -> None:
    assets = discover_assets()
    frequency_15m = [asset for asset in assets if asset.frequency == "15min"]
    assert frequency_15m
    asset_classes = {asset.asset_class for asset in frequency_15m}
    assert {"equities", "commodities", "crypto"}.issubset(asset_classes)


def test_schema_validation_for_representative_15m_files() -> None:
    representative_paths = [
        DATA_ROOT / "15min" / "equities" / "AAPL_15mins_2016-02-26_2026-03-01.csv",
        DATA_ROOT / "15min" / "commodities" / "COMMODITIES_GLD_15m.csv",
        DATA_ROOT / "15min" / "crypto" / "BTCUSDT.csv",
    ]
    assets = {asset.path: asset for asset in discover_assets()}

    for path in representative_paths:
        raw = load_raw_csv(path)
        normalized = normalize_ohlcv_frame(raw, assets[path])
        validation = validate_ohlcv_schema(normalized)
        assert validation.rows > 0
        assert normalized.columns.tolist() == [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "asset",
            "asset_class",
            "frequency",
            "source_file",
        ]


def test_data_manifest_can_be_built(tmp_path: Path) -> None:
    output_dir = tmp_path / "manifests"
    manifest_path = build_data_manifest(output_dir=output_dir)
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["asset_count"] >= 3
    assert any(asset["frequency"] == "15min" for asset in manifest["assets"])
    assert any(asset["asset_class"] == "crypto" for asset in manifest["assets"])


def test_global_split_boundaries_are_deterministic(tmp_path: Path) -> None:
    output_dir = tmp_path / "splits"
    first = build_global_split_manifest(output_dir=output_dir)
    second = build_global_split_manifest(output_dir=output_dir)
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")

    manifest = json.loads(first.read_text(encoding="utf-8"))
    boundaries = manifest["split_boundaries"]
    assert boundaries["train"]["start"] < boundaries["train"]["end"]
    assert boundaries["validation"]["start"] < boundaries["validation"]["end"]
    assert boundaries["test"]["start"] < boundaries["test"]["end"]
    assert boundaries["train"]["end"] < boundaries["validation"]["start"]
    assert boundaries["validation"]["end"] < boundaries["test"]["start"]


# ── Tests for unified CSV export and DataSplitter ──────────────


def test_export_unified_csvs_creates_files(tmp_path: Path) -> None:
    """Verify unified CSV export writes one file per asset."""
    output_dir = tmp_path / "unified"
    paths = build_unified_csvs(output_dir=output_dir)
    assert paths
    for p in paths:
        assert p.exists()
        assert p.suffix == ".csv"
        df = pd.read_csv(p)
        assert "timestamp" in df.columns
        assert "asset" in df.columns
        assert len(df) > 0


def test_unified_csvs_are_sorted(tmp_path: Path) -> None:
    """Ensure exported CSVs have timestamps in ascending order."""
    output_dir = tmp_path / "unified"
    paths = build_unified_csvs(output_dir=output_dir)
    for p in paths[:3]:  # check first 3 to keep test fast
        df = pd.read_csv(p)
        timestamps = pd.to_datetime(df["timestamp"])
        assert timestamps.is_monotonic_increasing, f"{p.name} not sorted"


def test_data_splitter_partitions_without_leakage(tmp_path: Path) -> None:
    """DataSplitter must produce non-overlapping, chronological partitions."""
    output_dir = tmp_path / "unified"
    paths = build_unified_csvs(output_dir=output_dir)
    # Pick an asset with enough rows
    big = max(paths, key=lambda p: p.stat().st_size)
    df = pd.read_csv(big)

    splitter = DataSplitter()
    result = splitter.split(df)

    summary = result.summary()
    assert summary["train"] > 0
    assert summary["validation"] > 0
    assert summary["test"] > 0

    # No leakage: train end < val start < test start
    if not result.train.empty and not result.validation.empty:
        train_max = pd.to_datetime(result.train["timestamp"]).max()
        val_min = pd.to_datetime(result.validation["timestamp"]).min()
        assert train_max < val_min, "Train/validation overlap detected"

    if not result.validation.empty and not result.test.empty:
        val_max = pd.to_datetime(result.validation["timestamp"]).max()
        test_min = pd.to_datetime(result.test["timestamp"]).min()
        assert val_max < test_min, "Validation/test overlap detected"
