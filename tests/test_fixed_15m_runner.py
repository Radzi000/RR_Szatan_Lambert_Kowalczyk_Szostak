from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from preprocessing import materialize_processed_data
from strategy_development.local_implementation.run_fixed_15m_experiments import (
    TABLE_NAMES,
    run_fixed_15m_experiments,
)


def test_processed_contract_is_materialized_and_deterministic() -> None:
    first = materialize_processed_data()
    second = materialize_processed_data()

    manifest_path = Path(first["manifest_path"])
    split_manifest_path = Path(first["split_manifest_path"])

    assert manifest_path.exists()
    assert split_manifest_path.exists()
    assert Path("data/processed/unified").exists()
    assert Path("data/processed/splits/csv").exists()
    assert any(Path("data/processed/unified").glob("*.csv"))
    assert any(Path("data/processed/splits/csv").glob("*.csv"))
    assert manifest_path.read_text(encoding="utf-8") == Path(second["manifest_path"]).read_text(
        encoding="utf-8"
    )
    assert split_manifest_path.read_text(encoding="utf-8") == Path(
        second["split_manifest_path"]
    ).read_text(encoding="utf-8")

    split_manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    assert (
        split_manifest["split_boundaries"]["train"]["end"]
        < split_manifest["split_boundaries"]["validation"]["start"]
    )
    assert (
        split_manifest["split_boundaries"]["validation"]["end"]
        < split_manifest["split_boundaries"]["test"]["start"]
    )


def test_fixed_15m_runner_smoke_outputs(tmp_path: Path) -> None:
    paths = run_fixed_15m_experiments(
        output_dir=tmp_path,
        assets={"AAPL", "GLD", "BTCUSDT"},
        materialize=True,
    )

    for path in paths.values():
        assert path.exists()

    summary = pd.read_csv(tmp_path / "tables" / TABLE_NAMES["summary"])
    split_summary = pd.read_csv(tmp_path / "tables" / TABLE_NAMES["split_summary"])
    returns = pd.read_csv(tmp_path / "tables" / TABLE_NAMES["returns"])
    trades = pd.read_csv(tmp_path / "tables" / TABLE_NAMES["trades"])

    assert set(summary["asset"]) == {"AAPL", "GLD", "BTCUSDT"}
    assert len(summary["strategy"].unique()) == 5
    assert set(split_summary["split"]) == {"train", "validation", "test"}
    assert {"asset", "asset_class", "strategy", "split", "timestamp", "equity", "return_pct"} == set(returns.columns)
    assert {"asset", "asset_class", "strategy", "split", "trade_id"} <= set(trades.columns)


def test_local_implementation_has_no_quantconnect_imports() -> None:
    root = Path("strategy_development/local_implementation")
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*(from|import)\s+QuantConnect\b", text, flags=re.MULTILINE):
            offenders.append(str(path))
        if re.search(r"\bQCAlgorithm\b", text):
            offenders.append(str(path))
    assert not offenders


def test_fixed_15m_runner_uses_no_live_download_path() -> None:
    runner_text = Path(
        "strategy_development/local_implementation/run_fixed_15m_experiments.py"
    ).read_text(encoding="utf-8")
    assert "yfinance" not in runner_text
    assert "DataProvider" not in runner_text
