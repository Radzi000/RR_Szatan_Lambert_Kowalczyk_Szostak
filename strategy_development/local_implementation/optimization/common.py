"""Shared Workstream C optimization utilities."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from preprocessing import materialize_processed_data
from preprocessing.loader import load_split

from ..backtest.engine import BacktestEngine, BacktestResult
from ..reproduce import PROJECT_ROOT
from ..strategy_specs import STRATEGY_SPECS, StrategySpec
from .io import params_to_json
from .metrics import MetricBundle, compute_metric_bundle, overfit_warning
from .param_spaces import PARAM_SPACES, ParamSpace

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
ALLOWED_OPT_SPLITS = ("train", "val")
SMOKE_ASSETS = ("AAPL", "GLD", "BTCUSDT")
TABLE_FILENAMES = {
    "search_results": "optimization_search_results.csv",
    "selected_params": "selected_params.csv",
    "comparison": "train_validation_comparison.csv",
    "verification": "optimization_verification_metrics.csv",
}


@dataclass(frozen=True)
class StrategyRunConfig:
    strategy_number: int
    strategy_key: str
    optimizer: str

    @property
    def spec(self) -> StrategySpec:
        return STRATEGY_SPECS[self.strategy_number]

    @property
    def script_name(self) -> str:
        return f"strategy{self.strategy_number + 1}_{self.optimizer.lower()}"


def default_strategy_configs() -> list[StrategyRunConfig]:
    return [
        StrategyRunConfig(0, "Strategy0", "NES"),
        StrategyRunConfig(1, "Strategy1", "NES"),
        StrategyRunConfig(2, "Strategy2", "NES"),
        StrategyRunConfig(3, "Strategy3", "CMA-ES"),
        StrategyRunConfig(4, "Strategy4", "CMA-ES"),
    ]


def parse_asset_list(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-iters", type=int, default=8, help="Number of optimization iterations.")
    parser.add_argument("--population", type=int, default=8, help="Population size per iteration.")
    parser.add_argument(
        "--assets",
        default="",
        help="Optional comma-separated asset allowlist, e.g. AAPL,GLD,BTCUSDT.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic optimization seed.")
    parser.add_argument("--smoke", action="store_true", help="Run a small smoke configuration.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where optimization outputs will be written.",
    )


def _discover_assets(assets: set[str] | None, smoke: bool) -> list[tuple[str, str]]:
    manifest = json.loads(
        (PROJECT_ROOT / "data" / "processed" / "manifests" / "data_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    selected: list[tuple[str, str]] = []
    for row in manifest["assets"]:
        if row["frequency"] != "15min":
            continue
        asset = row["asset"]
        asset_class = row["asset_class"]
        if assets and asset not in assets:
            continue
        if smoke and asset not in SMOKE_ASSETS:
            continue
        selected.append((asset, asset_class))
    return sorted(set(selected), key=lambda item: (item[1], item[0]))


def _to_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True)
    normalized = normalized.sort_values("timestamp").set_index("timestamp")
    normalized.index = normalized.index.tz_convert("US/Eastern")
    market = normalized.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    return market[["Open", "High", "Low", "Close", "Volume"]]


def _build_daily_data(minute_data: pd.DataFrame) -> pd.DataFrame:
    daily = (
        minute_data.assign(session_date=minute_data.index.date)
        .groupby("session_date")
        .agg(
            Open=("Open", "first"),
            High=("High", "max"),
            Low=("Low", "min"),
            Close=("Close", "last"),
            Volume=("Volume", "sum"),
        )
    )
    daily.index = pd.to_datetime(daily.index)
    daily.index.name = "Date"
    return daily


def load_optimization_splits(asset: str, asset_class: str) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    """Load train/validation only. Test is intentionally excluded."""
    if "test" in ALLOWED_OPT_SPLITS:
        raise RuntimeError("Optimization split contract violated: test split must never be loaded.")

    result: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    mapping = {"train": "train", "validation": "val"}
    for split_name, partition_name in mapping.items():
        raw = load_split(asset, asset_class, "15min", partition_name)
        minute_data = _to_market_frame(raw)
        result[split_name] = (_build_daily_data(minute_data), minute_data)
    return result


def run_backtest_for_params(
    strategy_cls: type,
    params: dict[str, Any],
    daily_data: pd.DataFrame,
    minute_data: pd.DataFrame,
) -> tuple[BacktestResult, MetricBundle]:
    engine = BacktestEngine(initial_capital=100_000.0, commission_per_share=0.005)
    result = engine.run(strategy_cls(**params), daily_data, minute_data)
    return result, compute_metric_bundle(result, minute_data)


def _valid_metric_bundle(metrics: MetricBundle) -> bool:
    numeric_values = [
        metrics.total_return,
        metrics.annualized_return,
        metrics.annualized_volatility,
        metrics.sharpe,
        metrics.sortino,
        metrics.max_drawdown,
        metrics.calmar,
        metrics.hit_rate,
        metrics.turnover,
        metrics.average_trade_pnl,
        metrics.exposure_time,
    ]
    if metrics.trade_count <= 0:
        return False
    if any(not np.isfinite(value) for value in numeric_values):
        return False
    return True


def _candidate_row(
    *,
    strategy: str,
    optimizer: str,
    asset: str,
    asset_class: str,
    iteration: int,
    candidate_id: int,
    params: dict[str, Any],
    metrics: MetricBundle,
    valid: bool,
) -> dict[str, object]:
    return {
        "strategy": strategy,
        "optimizer": optimizer,
        "asset": asset,
        "asset_class": asset_class,
        "frequency": "15min",
        "iteration": iteration,
        "candidate_id": candidate_id,
        "params_json": params_to_json(params),
        "train_sharpe": round(metrics.sharpe, 6),
        "train_return": round(metrics.total_return, 6),
        "train_volatility": round(metrics.annualized_volatility, 6),
        "train_max_drawdown": round(metrics.max_drawdown, 6),
        "train_trade_count": int(metrics.trade_count),
        "valid": bool(valid),
    }


def _verification_row(
    *,
    strategy: str,
    optimizer: str,
    asset: str,
    split: str,
    metrics: MetricBundle,
    config_source: str,
) -> dict[str, object]:
    row = {
        "strategy": strategy,
        "optimizer": optimizer,
        "asset": asset,
        "split": split,
        "total_return": round(metrics.total_return, 6),
        "annualized_return": round(metrics.annualized_return, 6),
        "annualized_volatility": round(metrics.annualized_volatility, 6),
        "sharpe": round(metrics.sharpe, 6),
        "sortino": round(metrics.sortino, 6),
        "max_drawdown": round(metrics.max_drawdown, 6),
        "calmar": round(metrics.calmar, 6),
        "hit_rate": round(metrics.hit_rate, 6),
        "turnover": round(metrics.turnover, 6),
        "trade_count": int(metrics.trade_count),
        "average_trade_pnl": round(metrics.average_trade_pnl, 6),
        "exposure_time": round(metrics.exposure_time, 6),
    }
    row["config_source"] = config_source
    return row


def _evaluate_candidates_on_validation(
    candidates: list[dict[str, Any]],
    strategy_cls: type,
    validation_daily: pd.DataFrame,
    validation_minute: pd.DataFrame,
) -> list[tuple[dict[str, Any], MetricBundle]]:
    evaluated: list[tuple[dict[str, Any], MetricBundle]] = []
    seen: set[str] = set()
    for params in candidates:
        encoded = params_to_json(params)
        if encoded in seen:
            continue
        seen.add(encoded)
        _, metrics = run_backtest_for_params(strategy_cls, params, validation_daily, validation_minute)
        evaluated.append((params, metrics))
    return evaluated


def _select_by_validation(candidates: list[tuple[dict[str, Any], MetricBundle]]) -> tuple[dict[str, Any], MetricBundle]:
    valid = [item for item in candidates if _valid_metric_bundle(item[1])]
    if valid:
        return max(valid, key=lambda item: (item[1].sharpe, item[1].total_return))
    return max(candidates, key=lambda item: item[1].sharpe)


def _run_nes(
    *,
    strategy_cls: type,
    param_space: ParamSpace,
    daily_data: pd.DataFrame,
    minute_data: pd.DataFrame,
    max_iters: int,
    population: int,
    seed: int,
    strategy_label: str,
    optimizer_label: str,
    asset: str,
    asset_class: str,
) -> tuple[list[dict[str, object]], list[dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    bounds_low = np.array(param_space.bounds_low, dtype=float)
    bounds_high = np.array(param_space.bounds_high, dtype=float)
    ranges = bounds_high - bounds_low
    ranges[ranges < 1e-12] = 1.0
    mean = (np.array(param_space.defaults, dtype=float) - bounds_low) / ranges
    mean = np.clip(mean, 0.05, 0.95)
    sigma = 0.18
    lr = 0.22
    search_rows: list[dict[str, object]] = []
    candidate_params: list[dict[str, Any]] = []
    candidate_id = 0
    population = max(population, 2)
    if population % 2 != 0:
        population += 1

    for iteration in range(max_iters):
        epsilons = rng.normal(0.0, 1.0, size=(population // 2, param_space.dimension))
        samples = np.vstack([epsilons, -epsilons])
        rewards: list[float] = []
        for epsilon in samples:
            candidate_id += 1
            normalized = np.clip(mean + sigma * epsilon, 0.0, 1.0)
            raw = bounds_low + normalized * ranges
            params = param_space.clip_and_round(raw.tolist())
            _, metrics = run_backtest_for_params(strategy_cls, params, daily_data, minute_data)
            valid = _valid_metric_bundle(metrics)
            reward = metrics.sharpe if valid else -1e6
            rewards.append(reward)
            candidate_params.append(params)
            search_rows.append(
                _candidate_row(
                    strategy=strategy_label,
                    optimizer=optimizer_label,
                    asset=asset,
                    asset_class=asset_class,
                    iteration=iteration,
                    candidate_id=candidate_id,
                    params=params,
                    metrics=metrics,
                    valid=valid,
                )
            )

        reward_array = np.array(rewards, dtype=float)
        standardized = reward_array - reward_array.mean()
        reward_std = reward_array.std()
        if reward_std > 1e-12:
            standardized /= reward_std
        gradient = np.dot(samples.T, standardized) / len(samples)
        mean = np.clip(mean + (lr / max(sigma, 1e-9)) * gradient, 0.0, 1.0)
        sigma = max(sigma * 0.97, 0.04)

    return search_rows, candidate_params


def _run_cmaes(
    *,
    strategy_cls: type,
    param_space: ParamSpace,
    daily_data: pd.DataFrame,
    minute_data: pd.DataFrame,
    max_iters: int,
    population: int,
    seed: int,
    strategy_label: str,
    optimizer_label: str,
    asset: str,
    asset_class: str,
) -> tuple[list[dict[str, object]], list[dict[str, Any]]]:
    bounds_low = np.array(param_space.bounds_low, dtype=float)
    bounds_high = np.array(param_space.bounds_high, dtype=float)
    ranges = bounds_high - bounds_low
    ranges[ranges < 1e-12] = 1.0
    mean0 = (np.array(param_space.defaults, dtype=float) - bounds_low) / ranges
    mean0 = np.clip(mean0, 0.05, 0.95)
    search_rows: list[dict[str, object]] = []
    candidate_params: list[dict[str, Any]] = []
    candidate_id = 0

    try:
        from cmaes import CMA

        optimizer = CMA(
            mean=mean0,
            sigma=0.22,
            bounds=np.column_stack([np.zeros(param_space.dimension), np.ones(param_space.dimension)]),
            population_size=max(population, 4),
            seed=seed,
        )

        for iteration in range(max_iters):
            solutions: list[tuple[np.ndarray, float]] = []
            for _ in range(optimizer.population_size):
                candidate_id += 1
                vector = optimizer.ask()
                raw = bounds_low + np.clip(vector, 0.0, 1.0) * ranges
                params = param_space.clip_and_round(raw.tolist())
                _, metrics = run_backtest_for_params(strategy_cls, params, daily_data, minute_data)
                valid = _valid_metric_bundle(metrics)
                reward = metrics.sharpe if valid else -1e6
                candidate_params.append(params)
                search_rows.append(
                    _candidate_row(
                        strategy=strategy_label,
                        optimizer=optimizer_label,
                        asset=asset,
                        asset_class=asset_class,
                        iteration=iteration,
                        candidate_id=candidate_id,
                        params=params,
                        metrics=metrics,
                        valid=valid,
                    )
                )
                solutions.append((vector, -reward))
            optimizer.tell(solutions)
    except ModuleNotFoundError:
        rng = np.random.default_rng(seed)
        mean = mean0.copy()
        sigma = 0.22
        population_size = max(population, 4)
        covariance = np.eye(param_space.dimension)

        for iteration in range(max_iters):
            vectors: list[np.ndarray] = []
            rewards: list[float] = []
            metrics_by_vector: list[tuple[dict[str, Any], MetricBundle, bool]] = []
            for _ in range(population_size):
                candidate_id += 1
                step = rng.multivariate_normal(np.zeros(param_space.dimension), covariance)
                vector = np.clip(mean + sigma * step, 0.0, 1.0)
                raw = bounds_low + vector * ranges
                params = param_space.clip_and_round(raw.tolist())
                _, metrics = run_backtest_for_params(strategy_cls, params, daily_data, minute_data)
                valid = _valid_metric_bundle(metrics)
                reward = metrics.sharpe if valid else -1e6
                vectors.append(vector)
                rewards.append(reward)
                metrics_by_vector.append((params, metrics, valid))
                candidate_params.append(params)
                search_rows.append(
                    _candidate_row(
                        strategy=strategy_label,
                        optimizer=optimizer_label,
                        asset=asset,
                        asset_class=asset_class,
                        iteration=iteration,
                        candidate_id=candidate_id,
                        params=params,
                        metrics=metrics,
                        valid=valid,
                    )
                )

            ranked = sorted(
                zip(vectors, rewards, metrics_by_vector),
                key=lambda item: item[1],
                reverse=True,
            )
            elite_count = max(2, population_size // 2)
            elite_vectors = np.array([item[0] for item in ranked[:elite_count]], dtype=float)
            mean = np.clip(elite_vectors.mean(axis=0), 0.0, 1.0)
            if elite_vectors.shape[0] > 1:
                covariance = np.cov(elite_vectors.T) + np.eye(param_space.dimension) * 1e-4
            sigma = max(sigma * 0.95, 0.05)

    return search_rows, candidate_params


def run_strategy_optimization(
    config: StrategyRunConfig,
    *,
    max_iters: int,
    population: int,
    seed: int,
    smoke: bool,
    output_dir: Path,
    assets: set[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Run optimization for one strategy across selected 15-minute assets."""
    materialize_processed_data()

    strategy_spec = config.spec
    strategy_cls = strategy_spec.factory
    param_space = PARAM_SPACES[config.strategy_key]
    search_rows: list[dict[str, object]] = []
    selected_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []
    verification_rows: list[dict[str, object]] = []

    selected_assets = _discover_assets(assets, smoke)
    if not selected_assets:
        raise ValueError("No 15-minute assets selected for optimization.")

    if smoke:
        max_iters = min(max_iters, 2)
        population = min(max(population, 4), 4)

    for asset, asset_class in selected_assets:
        split_data = load_optimization_splits(asset, asset_class)
        train_daily, train_minute = split_data["train"]
        validation_daily, validation_minute = split_data["validation"]

        baseline_train_result, baseline_train_metrics = run_backtest_for_params(
            strategy_cls, strategy_spec.params, train_daily, train_minute
        )
        baseline_validation_result, baseline_validation_metrics = run_backtest_for_params(
            strategy_cls, strategy_spec.params, validation_daily, validation_minute
        )
        verification_rows.extend(
            [
                _verification_row(
                    strategy=strategy_spec.label,
                    optimizer=config.optimizer,
                    asset=asset,
                    split="train",
                    metrics=baseline_train_metrics,
                    config_source="baseline",
                ),
                _verification_row(
                    strategy=strategy_spec.label,
                    optimizer=config.optimizer,
                    asset=asset,
                    split="validation",
                    metrics=baseline_validation_metrics,
                    config_source="baseline",
                ),
            ]
        )

        if config.optimizer == "NES":
            asset_search_rows, candidate_params = _run_nes(
                strategy_cls=strategy_cls,
                param_space=param_space,
                daily_data=train_daily,
                minute_data=train_minute,
                max_iters=max_iters,
                population=population,
                seed=seed,
                strategy_label=strategy_spec.label,
                optimizer_label=config.optimizer,
                asset=asset,
                asset_class=asset_class,
            )
        else:
            asset_search_rows, candidate_params = _run_cmaes(
                strategy_cls=strategy_cls,
                param_space=param_space,
                daily_data=train_daily,
                minute_data=train_minute,
                max_iters=max_iters,
                population=population,
                seed=seed,
                strategy_label=strategy_spec.label,
                optimizer_label=config.optimizer,
                asset=asset,
                asset_class=asset_class,
            )
        search_rows.extend(asset_search_rows)
        validation_candidates = _evaluate_candidates_on_validation(
            candidate_params, strategy_cls, validation_daily, validation_minute
        )
        selected_params, selected_validation_metrics = _select_by_validation(validation_candidates)
        optimized_train_result, optimized_train_metrics = run_backtest_for_params(
            strategy_cls, selected_params, train_daily, train_minute
        )
        optimized_validation_result, optimized_validation_metrics = run_backtest_for_params(
            strategy_cls, selected_params, validation_daily, validation_minute
        )
        verification_rows.extend(
            [
                _verification_row(
                    strategy=strategy_spec.label,
                    optimizer=config.optimizer,
                    asset=asset,
                    split="train",
                    metrics=optimized_train_metrics,
                    config_source="optimized",
                ),
                _verification_row(
                    strategy=strategy_spec.label,
                    optimizer=config.optimizer,
                    asset=asset,
                    split="validation",
                    metrics=optimized_validation_metrics,
                    config_source="optimized",
                ),
            ]
        )

        selected_rows.append(
            {
                "strategy": strategy_spec.label,
                "optimizer": config.optimizer,
                "asset": asset,
                "asset_class": asset_class,
                "frequency": "15min",
                "selected_by": "validation_sharpe",
                "params_json": params_to_json(selected_params),
                "train_sharpe": round(optimized_train_metrics.sharpe, 6),
                "validation_sharpe": round(selected_validation_metrics.sharpe, 6),
                "train_return": round(optimized_train_metrics.total_return, 6),
                "validation_return": round(selected_validation_metrics.total_return, 6),
                "train_max_drawdown": round(optimized_train_metrics.max_drawdown, 6),
                "validation_max_drawdown": round(selected_validation_metrics.max_drawdown, 6),
                "train_trade_count": int(optimized_train_metrics.trade_count),
                "validation_trade_count": int(selected_validation_metrics.trade_count),
            }
        )

        comparison_rows.append(
            {
                "strategy": strategy_spec.label,
                "optimizer": config.optimizer,
                "asset": asset,
                "asset_class": asset_class,
                "baseline_train_sharpe": round(baseline_train_metrics.sharpe, 6),
                "optimized_train_sharpe": round(optimized_train_metrics.sharpe, 6),
                "baseline_validation_sharpe": round(baseline_validation_metrics.sharpe, 6),
                "optimized_validation_sharpe": round(optimized_validation_metrics.sharpe, 6),
                "baseline_train_return": round(baseline_train_metrics.total_return, 6),
                "optimized_train_return": round(optimized_train_metrics.total_return, 6),
                "baseline_validation_return": round(baseline_validation_metrics.total_return, 6),
                "optimized_validation_return": round(optimized_validation_metrics.total_return, 6),
                "baseline_validation_max_drawdown": round(
                    baseline_validation_metrics.max_drawdown, 6
                ),
                "optimized_validation_max_drawdown": round(
                    optimized_validation_metrics.max_drawdown, 6
                ),
                "improvement_validation_sharpe": round(
                    optimized_validation_metrics.sharpe - baseline_validation_metrics.sharpe,
                    6,
                ),
                "overfit_warning": overfit_warning(
                    baseline_validation_sharpe=baseline_validation_metrics.sharpe,
                    optimized_train_sharpe=optimized_train_metrics.sharpe,
                    optimized_validation_sharpe=optimized_validation_metrics.sharpe,
                ),
            }
        )

    return {
        "search_results": pd.DataFrame(search_rows),
        "selected_params": pd.DataFrame(selected_rows),
        "comparison": pd.DataFrame(comparison_rows),
        "verification": pd.DataFrame(verification_rows),
    }
