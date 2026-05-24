"""Deterministic preprocessing utilities for committed research data.

Provides data discovery, schema validation, global time-based splitting,
unified CSV export, and a :class:`DataSplitter` for partitioning
DataFrames into train/validation/test sets without data leakage.
"""

from .validate_schema import normalize_ohlcv_frame, validate_ohlcv_schema


def build_data_manifest(*args, **kwargs):
    """Lazily dispatch to the data-manifest builder."""
    from .build_data_manifest import build_data_manifest as _build_data_manifest

    return _build_data_manifest(*args, **kwargs)


def build_global_split_manifest(*args, **kwargs):
    """Lazily dispatch to the global split builder."""
    from .make_global_splits import build_global_split_manifest as _build_global_split_manifest

    return _build_global_split_manifest(*args, **kwargs)


def discover_data_files(*args, **kwargs):
    """Lazily dispatch to the raw data discovery helper."""
    from .build_data_manifest import discover_data_files as _discover_data_files

    return _discover_data_files(*args, **kwargs)


def export_unified_csvs(*args, **kwargs):
    """Lazily dispatch to the unified CSV exporter."""
    from .export_unified import export_unified_csvs as _export

    return _export(*args, **kwargs)


__all__ = [
    "build_data_manifest",
    "build_global_split_manifest",
    "discover_data_files",
    "export_unified_csvs",
    "normalize_ohlcv_frame",
    "validate_ohlcv_schema",
]
