"""Deterministic preprocessing utilities for committed research data."""

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


__all__ = [
    "build_data_manifest",
    "build_global_split_manifest",
    "discover_data_files",
    "normalize_ohlcv_frame",
    "validate_ohlcv_schema",
]
