from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from strategy_development.local_implementation.optimization import common as optimization_common
from strategy_development.local_implementation.optimization import run_all_optimizations
from strategy_development.local_implementation.optimization import run_strategy1_nes
from strategy_development.local_implementation.optimization import run_strategy2_nes
from strategy_development.local_implementation.optimization import run_strategy3_nes
from strategy_development.local_implementation.optimization import run_strategy4_cmaes
from strategy_development.local_implementation.optimization import run_strategy5_cmaes


EXPECTED_TABLES = {
    "optimization_search_results.csv",
    "selected_params.csv",
    "train_validation_comparison.csv",
    "optimization_verification_metrics.csv",
}


def _stub_result_frames() -> dict[str, pd.DataFrame]:
    return {
        "search_results": pd.DataFrame(
            [
                {
                    "strategy": "Strategy0 / Baseline",
                    "optimizer": "NES",
                    "asset": "AAPL",
                    "asset_class": "equities",
                    "frequency": "15min",
                    "iteration": 0,
                    "candidate_id": 1,
                    "params_json": "{\"lookback\": 14}",
                    "train_sharpe": 1.0,
                    "train_return": 2.0,
                    "train_volatility": 3.0,
                    "train_max_drawdown": -1.0,
                    "train_trade_count": 4,
                    "valid": True,
                }
            ]
        ),
        "selected_params": pd.DataFrame(
            [
                {
                    "strategy": "Strategy0 / Baseline",
                    "optimizer": "NES",
                    "asset": "AAPL",
                    "asset_class": "equities",
                    "frequency": "15min",
                    "selected_by": "validation_sharpe",
                    "params_json": "{\"lookback\": 14}",
                    "train_sharpe": 1.0,
                    "validation_sharpe": 0.8,
                    "train_return": 2.0,
                    "validation_return": 1.0,
                    "train_max_drawdown": -1.0,
                    "validation_max_drawdown": -1.5,
                    "train_trade_count": 4,
                    "validation_trade_count": 3,
                }
            ]
        ),
        "comparison": pd.DataFrame(
            [
                {
                    "strategy": "Strategy0 / Baseline",
                    "optimizer": "NES",
                    "asset": "AAPL",
                    "asset_class": "equities",
                    "baseline_train_sharpe": 0.5,
                    "optimized_train_sharpe": 1.0,
                    "baseline_validation_sharpe": 0.4,
                    "optimized_validation_sharpe": 0.8,
                    "baseline_train_return": 1.0,
                    "optimized_train_return": 2.0,
                    "baseline_validation_return": 0.5,
                    "optimized_validation_return": 1.0,
                    "baseline_validation_max_drawdown": -2.0,
                    "optimized_validation_max_drawdown": -1.5,
                    "improvement_validation_sharpe": 0.4,
                    "overfit_warning": "none",
                }
            ]
        ),
        "verification": pd.DataFrame(
            [
                {
                    "strategy": "Strategy0 / Baseline",
                    "optimizer": "NES",
                    "asset": "AAPL",
                    "split": "train",
                    "total_return": 2.0,
                    "annualized_return": 10.0,
                    "annualized_volatility": 3.0,
                    "sharpe": 1.0,
                    "sortino": 1.2,
                    "max_drawdown": -1.0,
                    "calmar": 10.0,
                    "hit_rate": 0.5,
                    "turnover": 0.1,
                    "trade_count": 4,
                    "average_trade_pnl": 12.0,
                    "exposure_time": 0.3,
                    "config_source": "optimized",
                }
            ]
        ),
    }


@pytest.mark.parametrize(
    ("module_runner", "subdir"),
    [
        (run_strategy1_nes, "strategy1_nes"),
        (run_strategy2_nes, "strategy2_nes"),
        (run_strategy3_nes, "strategy3_nes"),
        (run_strategy4_cmaes, "strategy4_cmaes"),
        (run_strategy5_cmaes, "strategy5_cmaes"),
    ],
)
def test_strategy_optimization_scripts_support_smoke_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module_runner,
    subdir: str,
) -> None:
    monkeypatch.setattr(module_runner, "run_strategy_optimization", lambda *args, **kwargs: _stub_result_frames())
    exit_code = module_runner.main(
        [
            "--smoke",
            "--assets",
            "AAPL",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 0

    tables_dir = tmp_path / "optimization" / subdir / "tables"
    for filename in EXPECTED_TABLES:
        assert (tables_dir / filename).exists()


def test_aggregate_optimization_runner_smoke_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_calls: list[str] = []

    def fake_run_strategy_optimization(config, **kwargs):
        run_calls.append(config.strategy_key)
        return _stub_result_frames()

    monkeypatch.setattr(run_all_optimizations, "run_strategy_optimization", fake_run_strategy_optimization)
    exit_code = run_all_optimizations.main(
        [
            "--smoke",
            "--assets",
            "AAPL",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert len(run_calls) == 5

    tables_dir = tmp_path / "tables"
    figures_dir = tmp_path / "figures"
    for filename in EXPECTED_TABLES:
        assert (tables_dir / filename).exists()
    assert (figures_dir / "optimization_convergence.png").exists()
    assert (figures_dir / "train_validation_sharpe_comparison.png").exists()


def test_selected_params_schema_is_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        run_all_optimizations,
        "run_strategy_optimization",
        lambda *args, **kwargs: _stub_result_frames(),
    )
    run_all_optimizations.main(
        [
            "--smoke",
            "--assets",
            "AAPL",
            "--output-dir",
            str(tmp_path),
        ]
    )
    selected = pd.read_csv(tmp_path / "tables" / "selected_params.csv")
    assert set(selected.columns) == {
        "strategy",
        "optimizer",
        "asset",
        "asset_class",
        "frequency",
        "selected_by",
        "params_json",
        "train_sharpe",
        "validation_sharpe",
        "train_return",
        "validation_return",
        "train_max_drawdown",
        "validation_max_drawdown",
        "train_trade_count",
        "validation_trade_count",
    }
    assert selected["asset"].eq("AAPL").all()


def test_optimization_path_never_requests_test_split(monkeypatch: pytest.MonkeyPatch) -> None:
    requested_partitions: list[str] = []

    def fake_load_split(asset: str, asset_class: str, frequency: str, partition: str):
        requested_partitions.append(partition)
        assert partition != "test"
        return pd.read_csv(
            "data/processed/splits/csv/AAPL_equities_15min_train.csv"
            if partition == "train"
            else "data/processed/splits/csv/AAPL_equities_15min_val.csv"
        )

    monkeypatch.setattr(optimization_common, "load_split", fake_load_split)
    splits = optimization_common.load_optimization_splits("AAPL", "equities")
    assert set(splits) == {"train", "validation"}
    assert requested_partitions == ["train", "val"]
