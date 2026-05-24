"""Validation and normalization helpers for OHLCV data."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
RAW_COLUMN_MAP = {
    "date": "timestamp",
    "Date": "timestamp",
    "Datetime": "timestamp",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}


@dataclass(frozen=True)
class SchemaValidationResult:
    """Validation summary for one normalized dataset."""

    rows: int
    timestamp_min: str
    timestamp_max: str
    columns: tuple[str, ...]


def _parse_timestamp_series(series: pd.Series) -> pd.Series:
    """Parse heterogeneous timestamp formats into UTC timestamps."""
    text = series.astype(str)
    sample = next((value for value in text if value and value.lower() != "nan"), "")
    if sample.endswith("US/Eastern"):
        stripped = text.str.replace(" US/Eastern", "", regex=False)
        parsed = pd.to_datetime(stripped, format="%Y%m%d %H:%M:%S", utc=False)
        return parsed.dt.tz_localize("US/Eastern").dt.tz_convert("UTC")
    return pd.to_datetime(text, utc=True)


def normalize_ohlcv_frame(frame: pd.DataFrame, asset) -> pd.DataFrame:
    """Normalize a raw OHLCV frame to the shared schema."""
    normalized = frame.rename(columns=RAW_COLUMN_MAP).copy()
    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required columns after normalization for {asset.path}: {missing}")
    normalized = normalized[REQUIRED_COLUMNS].copy()
    normalized["timestamp"] = _parse_timestamp_series(normalized["timestamp"])
    normalized["asset"] = asset.asset
    normalized["asset_class"] = asset.asset_class
    normalized["frequency"] = asset.frequency
    normalized["source_file"] = str(asset.path.relative_to(asset.path.parents[2])).replace("\\", "/")
    return normalized


def validate_ohlcv_schema(frame: pd.DataFrame) -> SchemaValidationResult:
    """Validate the shared normalized OHLCV schema."""
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        msg = f"Missing required columns: {missing}"
        raise ValueError(msg)

    if frame.empty:
        raise ValueError("OHLCV frame is empty")

    if frame["timestamp"].isna().any():
        raise ValueError("Timestamp column contains missing values")

    for column in ["open", "high", "low", "close", "volume"]:
        if frame[column].isna().any():
            raise ValueError(f"Column '{column}' contains missing values")

    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("Timestamp column must be sorted in increasing order")

    return SchemaValidationResult(
        rows=len(frame),
        timestamp_min=str(frame["timestamp"].iloc[0]),
        timestamp_max=str(frame["timestamp"].iloc[-1]),
        columns=tuple(frame.columns),
    )
