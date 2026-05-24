from __future__ import annotations

import json
from pathlib import Path

from preprocessing import build_data_manifest, build_global_split_manifest, discover_data_files
from preprocessing.build_data_manifest import DATA_ROOT, discover_assets, load_raw_csv
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
