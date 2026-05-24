"""Load pre-split CSV files for direct use in strategies and backtests.

This is the main entry point for downstream code — no preprocessing
runs at import time; it just reads the pre-generated CSVs.

Example
-------
>>> from preprocessing.loader import load_split
>>> train = load_split("AAPL", "equities", "15min", "train")
>>> val   = load_split("AAPL", "equities", "15min", "val")
>>> test  = load_split("AAPL", "equities", "15min", "test")

>>> # Or load all three at once:
>>> from preprocessing.loader import load_all_splits
>>> splits = load_all_splits("BTCUSDT", "crypto", "15min")
>>> splits["train"].head()
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .build_data_manifest import DATA_ROOT

logger = logging.getLogger(__name__)

DEFAULT_SPLIT_CSV_DIR = DATA_ROOT / "processed" / "splits" / "csv"


def load_split(
    asset: str,
    asset_class: str,
    frequency: str,
    partition: str,
    split_dir: Path = DEFAULT_SPLIT_CSV_DIR,
) -> pd.DataFrame:
    """Load a single pre-split CSV.

    Parameters
    ----------
    asset : str
        Asset ticker (e.g. ``"AAPL"``, ``"BTCUSDT"``).
    asset_class : str
        One of ``"equities"``, ``"commodities"``, ``"crypto"``.
    frequency : str
        Data frequency (e.g. ``"15min"``, ``"1day"``).
    partition : str
        One of ``"train"``, ``"val"``, ``"test"``.
    split_dir : Path
        Directory containing the split CSVs.

    Returns
    -------
    pd.DataFrame
        The requested partition with a parsed ``timestamp`` column.

    Raises
    ------
    FileNotFoundError
        If the requested split CSV does not exist.
    """
    filename = f"{asset}_{asset_class}_{frequency}_{partition}.csv"
    path = split_dir / filename
    if not path.exists():
        msg = (
            f"Split CSV not found: {path}\n"
            f"Run `python -m preprocessing.export_splits` to generate."
        )
        raise FileNotFoundError(msg)

    df = pd.read_csv(path, parse_dates=["timestamp"])
    logger.info("Loaded %s — %d rows", filename, len(df))
    return df


def load_all_splits(
    asset: str,
    asset_class: str,
    frequency: str,
    split_dir: Path = DEFAULT_SPLIT_CSV_DIR,
) -> dict[str, pd.DataFrame]:
    """Load train, val, and test partitions for one asset.

    Parameters
    ----------
    asset : str
        Asset ticker.
    asset_class : str
        Asset class.
    frequency : str
        Data frequency.
    split_dir : Path
        Directory containing the split CSVs.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys: ``"train"``, ``"val"``, ``"test"``.
    """
    return {
        partition: load_split(asset, asset_class, frequency, partition, split_dir)
        for partition in ("train", "val", "test")
    }


def list_available_splits(
    split_dir: Path = DEFAULT_SPLIT_CSV_DIR,
) -> list[str]:
    """List all available split CSV filenames.

    Parameters
    ----------
    split_dir : Path
        Directory containing the split CSVs.

    Returns
    -------
    list[str]
        Sorted filenames.
    """
    if not split_dir.exists():
        return []
    return sorted(p.name for p in split_dir.glob("*.csv"))
