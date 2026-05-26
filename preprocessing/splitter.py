"""Load split boundaries and partition data into train/val/test sets.

The :class:`DataSplitter` reads the global split manifest produced by
:mod:`preprocessing.make_global_splits` and applies it to any unified
DataFrame with a ``timestamp`` column.  This avoids data leakage by
splitting strictly on time boundaries.

Example
-------
>>> from preprocessing.splitter import DataSplitter
>>> splitter = DataSplitter()
>>> train, val, test = splitter.split(unified_df)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .build_data_manifest import DATA_ROOT

logger = logging.getLogger(__name__)

DEFAULT_SPLIT_PATH = DATA_ROOT / "processed" / "splits" / "global_time_splits.json"


def load_split_manifest(split_manifest_path: Path = DEFAULT_SPLIT_PATH) -> dict[str, object]:
    """Load the raw split manifest JSON from disk."""
    return json.loads(split_manifest_path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class SplitBoundary:
    """Time boundaries for one data partition.

    Attributes
    ----------
    start : pd.Timestamp
        Inclusive start of the partition.
    end : pd.Timestamp
        Inclusive end of the partition.
    """

    start: pd.Timestamp
    end: pd.Timestamp


@dataclass(frozen=True)
class SplitResult:
    """Container for the three data partitions.

    Attributes
    ----------
    train : pd.DataFrame
        Training data (earliest period).
    validation : pd.DataFrame
        Validation data (middle period).
    test : pd.DataFrame
        Test data (latest period).
    boundaries : dict[str, SplitBoundary]
        The time boundaries used.
    """

    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    boundaries: dict[str, SplitBoundary]

    def summary(self) -> dict[str, int]:
        """Return row counts per partition."""
        return {
            "train": len(self.train),
            "validation": len(self.validation),
            "test": len(self.test),
            "total": len(self.train) + len(self.validation) + len(self.test),
        }


class DataSplitter:
    """Split DataFrames using the global time-based boundaries.

    Parameters
    ----------
    split_manifest_path : Path
        Path to ``global_time_splits.json``.  Defaults to the
        standard location under ``data/processed/splits/``.
    """

    def __init__(self, split_manifest_path: Path = DEFAULT_SPLIT_PATH) -> None:
        self.split_manifest_path = split_manifest_path
        self._boundaries = self._load_boundaries()

    def _load_boundaries(self) -> dict[str, SplitBoundary]:
        """Parse the split manifest JSON into typed boundaries."""
        raw = load_split_manifest(self.split_manifest_path)
        bounds = raw["split_boundaries"]
        result: dict[str, SplitBoundary] = {}
        for partition in ("train", "validation", "test"):
            result[partition] = SplitBoundary(
                start=pd.Timestamp(bounds[partition]["start"]),
                end=pd.Timestamp(bounds[partition]["end"]),
            )
        return result

    @property
    def boundaries(self) -> dict[str, SplitBoundary]:
        """The loaded time boundaries."""
        return self._boundaries

    def split(self, df: pd.DataFrame, timestamp_col: str = "timestamp") -> SplitResult:
        """Partition a DataFrame by the global time boundaries.

        Parameters
        ----------
        df : pd.DataFrame
            Data with a parseable timestamp column.
        timestamp_col : str
            Name of the timestamp column (default ``"timestamp"``).

        Returns
        -------
        SplitResult
            Named container with ``.train``, ``.validation``, and
            ``.test`` DataFrames plus the boundaries used.

        Raises
        ------
        KeyError
            If *timestamp_col* is missing from *df*.
        """
        if timestamp_col not in df.columns:
            msg = f"Column '{timestamp_col}' not found in DataFrame"
            raise KeyError(msg)

        ts = pd.to_datetime(df[timestamp_col], utc=True)
        b = self._boundaries

        train_mask = (ts >= b["train"].start) & (ts <= b["train"].end)
        val_mask = (ts >= b["validation"].start) & (ts <= b["validation"].end)
        test_mask = (ts >= b["test"].start) & (ts <= b["test"].end)

        result = SplitResult(
            train=df.loc[train_mask].copy(),
            validation=df.loc[val_mask].copy(),
            test=df.loc[test_mask].copy(),
            boundaries=self._boundaries,
        )

        logger.info(
            "Split complete: train=%d, val=%d, test=%d (total=%d, original=%d)",
            len(result.train),
            len(result.validation),
            len(result.test),
            len(result.train) + len(result.validation) + len(result.test),
            len(df),
        )
        return result
