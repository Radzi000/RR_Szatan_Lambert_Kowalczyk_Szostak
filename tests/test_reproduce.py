from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_development.local_implementation.data.provider import DataProvider
from strategy_development.local_implementation.reproduce import DATA_ROOT, run_reproduction


def test_package_imports_and_data_files_exist() -> None:
    assert (DATA_ROOT / "1day" / "spy_daily.csv").exists()
    assert (DATA_ROOT / "5min" / "spy_5m.csv").exists()


def test_committed_data_loads_without_downloads() -> None:
    provider = DataProvider(data_dir=DATA_ROOT, allow_download=False)
    minute = provider.get_data("1900-01-01", "2100-01-01", interval="5m", use_cache=False)
    daily = provider.get_daily_data("2025-12-01", "2026-05-04")

    assert not minute.empty
    assert not daily.empty
    assert minute.index.tz is not None
    assert {"Open", "High", "Low", "Close", "Volume"}.issubset(minute.columns)


def test_reproduction_pipeline_generates_stable_outputs(tmp_path: Path) -> None:
    run_reproduction(output_dir=tmp_path, generate_report=True)

    expected_paths = [
        tmp_path / "tables" / "strategy_summary.csv",
        tmp_path / "tables" / "strategy_summary.md",
        tmp_path / "tables" / "equity_curves_taken_strats.csv",
        tmp_path / "tables" / "drawdowns_taken_strats.csv",
        tmp_path / "tables" / "verification_metrics_taken_strats.csv",
        tmp_path / "tables" / "reproducibility_manifest.json",
        tmp_path / "figures" / "equity_curves.png",
        tmp_path / "figures" / "drawdowns.png",
        tmp_path / "figures" / "equity_curves_taken_strats.png",
        tmp_path / "figures" / "drawdowns_taken_strats.png",
        tmp_path / "report" / "final_report.md",
    ]
    for path in expected_paths:
        assert path.exists()

    summary = pd.read_csv(tmp_path / "tables" / "strategy_summary.csv")
    assert len(summary) == 5
    assert summary["strategy"].tolist() == [
        "Strategy0 / Baseline",
        "Strategy1 / Asymmetric Intervals",
        "Strategy2 / EMA Filter",
        "Strategy3 / Exit Confirmation",
        "Strategy4 / EMA + Confirmation",
    ]

    manifest = json.loads((tmp_path / "tables" / "reproducibility_manifest.json").read_text())
    assert manifest["run_command"] == "python -m strategy_development.local_implementation.reproduce"
    assert manifest["environment"]["internet_required_at_runtime"] is False
    assert manifest["transaction_costs_bps"]["equity_cost_bps"] == 1.0
