"""Build deterministic manifests for committed raw datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .validate_schema import normalize_ohlcv_frame, validate_ohlcv_schema

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_DIR = DATA_ROOT / "processed" / "manifests"


@dataclass(frozen=True)
class DataAsset:
    """Descriptor for one committed raw data file."""

    path: Path
    asset: str
    asset_class: str
    frequency: str


def sha256_file(path: Path) -> str:
    """Compute a SHA256 checksum for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_asset_metadata(path: Path, data_root: Path = DATA_ROOT) -> DataAsset:
    """Infer asset metadata from the current committed directory layout."""
    relative = path.relative_to(data_root)
    parts = relative.parts
    if parts[0] == "1day":
        return DataAsset(path=path, asset="SPY", asset_class="equities", frequency="1day")
    if parts[0] == "5min":
        return DataAsset(path=path, asset="SPY", asset_class="equities", frequency="5min")
    if parts[0] == "15min":
        asset_class = parts[1]
        stem = path.stem
        if asset_class == "equities":
            asset = stem.split("_")[0]
        elif asset_class == "commodities":
            asset = stem.split("_")[-2] if "_" in stem else stem
        else:
            asset = stem
        return DataAsset(path=path, asset=asset, asset_class=asset_class, frequency="15min")
    raise ValueError(f"Unsupported raw data path: {path}")


def discover_assets(data_root: Path = DATA_ROOT) -> list[DataAsset]:
    """Discover committed raw assets in a deterministic order."""
    files: list[Path] = []
    for relative_dir in [
        Path("1day"),
        Path("5min"),
        Path("15min") / "commodities",
        Path("15min") / "crypto",
        Path("15min") / "equities",
    ]:
        full_dir = data_root / relative_dir
        if full_dir.exists():
            files.extend(sorted(path for path in full_dir.glob("*.csv") if path.is_file()))
    return [infer_asset_metadata(path, data_root=data_root) for path in files]


def discover_data_files(data_root: Path = DATA_ROOT) -> list[DataAsset]:
    """Expose deterministic raw-data discovery for callers and tests."""
    return discover_assets(data_root=data_root)


def load_raw_csv(path: Path) -> pd.DataFrame:
    """Load a raw OHLCV CSV without mutating its original schema."""
    return pd.read_csv(path)


def get_session_profile(asset_class: str) -> dict[str, str | None]:
    """Return the documented session convention for an asset class."""
    if asset_class in {"equities", "commodities"}:
        return {
            "timezone": "US/Eastern",
            "session_type": "regular_us_session",
            "session_open": "09:30",
            "session_close": "16:00",
        }
    if asset_class == "crypto":
        return {
            "timezone": "UTC",
            "session_type": "continuous_24_7_adapted",
            "session_open": None,
            "session_close": None,
        }
    raise ValueError(f"Unsupported asset class: {asset_class}")


def build_data_manifest(
    data_root: Path = DATA_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """Build and write a deterministic manifest for committed raw data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = discover_data_files(data_root=data_root)

    manifest_assets: list[dict[str, object]] = []
    for asset in assets:
        raw = load_raw_csv(asset.path)
        normalized = normalize_ohlcv_frame(raw, asset)
        validation = validate_ohlcv_schema(normalized)
        session_profile = get_session_profile(asset.asset_class)
        manifest_assets.append(
            {
                "asset": asset.asset,
                "asset_class": asset.asset_class,
                "frequency": asset.frequency,
                "source_file": str(asset.path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "rows": validation.rows,
                "timestamp_min": validation.timestamp_min,
                "timestamp_max": validation.timestamp_max,
                "columns": list(validation.columns),
                "sha256": sha256_file(asset.path),
                "session_profile": session_profile,
            }
        )

    manifest = {
        "data_root": str(data_root.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "asset_count": len(manifest_assets),
        "assets": manifest_assets,
    }
    manifest_path = output_dir / "data_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def verify_data_manifest(
    manifest_path: Path = DEFAULT_OUTPUT_DIR / "data_manifest.json",
    project_root: Path = PROJECT_ROOT,
    *,
    strict: bool = True,
) -> list[dict[str, str]]:
    """Verify committed data files still match the SHA256 checksums in the manifest.

    For every asset listed in the manifest, recompute the SHA256 of its source
    file and compare it to the stored checksum. Returns a list of problem records
    (empty when everything matches). With ``strict=True`` it raises ``ValueError``
    if any file is missing or its checksum differs from the recorded one.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[dict[str, str]] = []
    for entry in manifest["assets"]:
        file_path = project_root / entry["source_file"]
        if not file_path.exists():
            problems.append(
                {
                    "source_file": entry["source_file"],
                    "problem": "missing",
                    "expected": entry["sha256"],
                    "actual": "",
                }
            )
            continue
        actual = sha256_file(file_path)
        if actual != entry["sha256"]:
            problems.append(
                {
                    "source_file": entry["source_file"],
                    "problem": "checksum_mismatch",
                    "expected": entry["sha256"],
                    "actual": actual,
                }
            )
    if strict and problems:
        details = "; ".join(f"{p['source_file']} ({p['problem']})" for p in problems)
        raise ValueError(f"Data integrity check failed against {manifest_path.name}: {details}")
    return problems


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deterministic data-manifest generation."""
    parser = argparse.ArgumentParser(description="Build a deterministic manifest for committed raw data.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where the manifest JSON should be written.",
    )
    args = parser.parse_args(argv)
    manifest_path = build_data_manifest(output_dir=Path(args.output_dir))
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
