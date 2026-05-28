"""Shared Workstream C optimization utilities."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from preprocessing import materialize_processed_data
from preprocessing.loader import load_split

from ..backtest.engine import BacktestEngine, BacktestResult
from ..costs import (
    DEFAULT_COST_CONFIG,
    TransactionCostConfig,
    add_cost_args,
    cost_config_from_args,
)
from ..reproduce import PROJECT_ROOT
from ..strategy_specs import STRATEGY_SPECS, StrategySpec
from .io import params_to_json
from .metrics import MetricBundle, compute_metric_bundle, overfit_warning
from .param_spaces import PARAM_SPACES, ParamSpace

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
ALLOWED_OPT_SPLITS = ("train", "val")
SMOKE_ASSETS = ("AAPL", "GLD", "BTCUSDT")
PRESENTATION_ASSETS = ("AAPL", "MSFT", "NVDA", "GLD", "USO", "BTCUSDT", "ETHUSDT")
TABLE_FILENAMES = {
    "search_results": "optimization_search_results.csv",
    "selected_params": "selected_params.csv",
    "comparison": "train_validation_comparison.csv",
    "verification": "optimization_verification_metrics.csv",
}
_PROCESSED_DATA_READY = False


@dataclass(frozen=True)
class RuntimeSettings:
    max_iters: int
    population: int
    smoke: bool
    asset_sample: str
    max_assets: int | None
    timeout_minutes: float | None
    validation_candidates: int | None
    mode: str


class RuntimeGuard:
    def __init__(self, timeout_minutes: float | None) -> None:
        self.started_at = time.perf_counter()
        self.timeout_seconds = None if timeout_minutes is None else timeout_minutes * 60.0

    def elapsed(self) -> float:
        return time.perf_counter() - self.started_at

    def check(self) -> None:
        if self.timeout_seconds is not None and self.elapsed() > self.timeout_seconds:
            minutes = self.timeout_seconds / 60.0
            raise TimeoutError(f"Optimization exceeded --timeout-minutes={minutes:g}.")


class ProgressLogger:
    def __init__(self, *, total_candidates: int, guard: RuntimeGuard) -> None:
        self.total_candidates = max(total_candidates, 1)
        self.guard = guard
        self.completed_candidates = 0

    def candidate_done(
        self,
        *,
        strategy: str,
        asset: str,
        optimizer: str,
        iteration: int,
        candidate: int,
        cached: bool,
    ) -> None:
        self.completed_candidates += 1
        elapsed = self.guard.elapsed()
        average = elapsed / max(self.completed_candidates, 1)
        remaining = max(self.total_candidates - self.completed_candidates, 0)
        eta = average * remaining
        cache_label = " cached" if cached else ""
        print(
            "[optimization] "
            f"strategy={strategy} asset={asset} optimizer={optimizer} "
            f"iteration={iteration + 1} candidate={candidate} "
            f"completed={self.completed_candidates}/{self.total_candidates} "
            f"elapsed={elapsed / 60.0:.1f}m eta={eta / 60.0:.1f}m{cache_label}",
            flush=True,
        )


class EvaluationCache:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str, str, float], tuple[BacktestResult, MetricBundle]] = {}

    def get(
        self,
        *,
        strategy: str,
        asset: str,
        split: str,
        params: dict[str, Any],
        cost_bps: float,
    ) -> tuple[BacktestResult, MetricBundle] | None:
        return self._items.get((strategy, asset, split, params_to_json(params), round(float(cost_bps), 6)))

    def set(
        self,
        *,
        strategy: str,
        asset: str,
        split: str,
        params: dict[str, Any],
        cost_bps: float,
        value: tuple[BacktestResult, MetricBundle],
    ) -> None:
        self._items[(strategy, asset, split, params_to_json(params), round(float(cost_bps), 6))] = value


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
    parser.add_argument("--max-iters", type=int, default=None, help="Number of optimization iterations.")
    parser.add_argument("--population", type=int, default=None, help="Population size per iteration.")
    parser.add_argument(
        "--assets",
        default="",
        help="Optional comma-separated asset allowlist, e.g. AAPL,GLD,BTCUSDT.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic optimization seed.")
    parser.add_argument("--smoke", action="store_true", help="Run a small smoke configuration.")
    parser.add_argument("--presentation", action="store_true", help="Run the practical presentation configuration.")
    parser.add_argument("--research", action="store_true", help="Opt in to all-asset research-scale optimization.")
    parser.add_argument("--max-assets", type=int, default=None, help="Maximum number of selected assets.")
    parser.add_argument(
        "--timeout-minutes",
        type=float,
        default=None,
        help="Stop the run after this many minutes.",
    )
    parser.add_argument(
        "--asset-sample",
        choices=["mode", "smoke", "presentation", "all"],
        default="mode",
        help="Asset sample to use when --assets is not provided.",
    )
    parser.add_argument(
        "--validation-candidates",
        type=int,
        default=None,
        help="Number of top train candidates to evaluate on validation per strategy/asset.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where optimization outputs will be written.",
    )
    add_cost_args(parser)


def runtime_settings_from_args(args: argparse.Namespace) -> RuntimeSettings:
    if args.smoke:
        mode = "smoke"
    elif args.research:
        mode = "research"
    else:
        mode = "presentation"

    defaults = {
        "smoke": {"max_iters": 1, "population": 2, "timeout_minutes": 10.0, "validation_candidates": 2},
        "presentation": {"max_iters": 2, "population": 4, "timeout_minutes": 120.0, "validation_candidates": 3},
        "research": {"max_iters": 8, "population": 8, "timeout_minutes": 360.0, "validation_candidates": None},
    }[mode]
    asset_sample = args.asset_sample
    if asset_sample == "mode":
        asset_sample = "all" if mode == "research" else mode
    return RuntimeSettings(
        max_iters=args.max_iters if args.max_iters is not None else int(defaults["max_iters"]),
        population=args.population if args.population is not None else int(defaults["population"]),
        smoke=mode == "smoke",
        asset_sample=asset_sample,
        max_assets=args.max_assets,
        timeout_minutes=(
            args.timeout_minutes
            if args.timeout_minutes is not None
            else float(defaults["timeout_minutes"])
        ),
        validation_candidates=(
            args.validation_candidates
            if args.validation_candidates is not None
            else defaults["validation_candidates"]
        ),
        mode=mode,
    )


def _discover_assets(
    assets: set[str] | None,
    smoke: bool,
    *,
    asset_sample: str = "all",
    max_assets: int | None = None,
) -> list[tuple[str, str]]:
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
        if not assets and smoke and asset not in SMOKE_ASSETS:
            continue
        if not assets and asset_sample == "smoke" and asset not in SMOKE_ASSETS:
            continue
        if not assets and asset_sample == "presentation" and asset not in PRESENTATION_ASSETS:
            continue
        selected.append((asset, asset_class))
    ordered = sorted(set(selected), key=lambda item: (item[1], item[0]))
    if max_assets is not None:
        ordered = ordered[:max_assets]
    return ordered


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


def ensure_processed_data_ready() -> None:
    global _PROCESSED_DATA_READY
    if _PROCESSED_DATA_READY:
        return
    required_paths = [
        PROJECT_ROOT / "data" / "processed" / "manifests" / "data_manifest.json",
        PROJECT_ROOT / "data" / "processed" / "splits" / "global_time_splits.json",
    ]
    if not all(path.exists() for path in required_paths):
        materialize_processed_data()
    _PROCESSED_DATA_READY = True


def _limit_split_history(
    split_data: dict[str, tuple[pd.DataFrame, pd.DataFrame]],
    *,
    max_bars: int | None,
) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    if max_bars is None:
        return split_data
    limited: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for split_name, (_, minute_data) in split_data.items():
        clipped_minute = minute_data.tail(max_bars).copy()
        limited[split_name] = (_build_daily_data(clipped_minute), clipped_minute)
    return limited


def run_backtest_for_params(
    strategy_cls: type,
    params: dict[str, Any],
    daily_data: pd.DataFrame,
    minute_data: pd.DataFrame,
) -> tuple[BacktestResult, MetricBundle]:
    return run_backtest_for_params_with_costs(
        strategy_cls,
        params,
        daily_data,
        minute_data,
        asset_class="default",
        cost_config=DEFAULT_COST_CONFIG,
    )


def build_cost_config_from_args(args: argparse.Namespace) -> TransactionCostConfig:
    return cost_config_from_args(args)


def run_backtest_for_params_with_costs(
    strategy_cls: type,
    params: dict[str, Any],
    daily_data: pd.DataFrame,
    minute_data: pd.DataFrame,
    *,
    asset_class: str,
    cost_config: TransactionCostConfig,
) -> tuple[BacktestResult, MetricBundle]:
    engine = BacktestEngine(initial_capital=100_000.0, cost_config=cost_config)
    result = engine.run(
        strategy_cls(**params),
        daily_data,
        minute_data,
        asset_class=asset_class,
        frequency="15min",
    )
    return result, compute_metric_bundle(result, minute_data)


def _evaluate_with_cache(
    *,
    cache: EvaluationCache,
    strategy_label: str,
    asset: str,
    split: str,
    strategy_cls: type,
    params: dict[str, Any],
    daily_data: pd.DataFrame,
    minute_data: pd.DataFrame,
    asset_class: str,
    cost_config: TransactionCostConfig,
) -> tuple[BacktestResult, MetricBundle, bool]:
    cached = cache.get(
        strategy=strategy_label,
        asset=asset,
        split=split,
        params=params,
        cost_bps=cost_config.cost_bps_for(asset_class),
    )
    if cached is not None:
        return cached[0], cached[1], True
    result = run_backtest_for_params_with_costs(
        strategy_cls,
        params,
        daily_data,
        minute_data,
        asset_class=asset_class,
        cost_config=cost_config,
    )
    cache.set(
        strategy=strategy_label,
        asset=asset,
        split=split,
        params=params,
        cost_bps=cost_config.cost_bps_for(asset_class),
        value=result,
    )
    return result[0], result[1], False


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
    cost_bps: float,
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
        "train_net_sharpe": round(metrics.net_sharpe, 6),
        "train_gross_sharpe": round(metrics.gross_sharpe, 6),
        "train_sharpe": round(metrics.net_sharpe, 6),
        "train_net_return": round(metrics.net_total_return, 6),
        "train_return": round(metrics.net_total_return, 6),
        "train_volatility": round(metrics.annualized_volatility, 6),
        "train_max_drawdown": round(metrics.max_drawdown, 6),
        "train_trade_count": int(metrics.trade_count),
        "train_total_cost": round(metrics.total_transaction_cost, 6),
        "train_turnover": round(metrics.turnover, 6),
        "cost_bps": round(float(cost_bps), 6),
        "valid": bool(valid),
    }


def _verification_row(
    *,
    strategy: str,
    optimizer: str,
    asset: str,
    asset_class: str,
    split: str,
    metrics: MetricBundle,
    config_source: str,
    cost_bps: float,
) -> dict[str, object]:
    row = {
        "strategy": strategy,
        "optimizer": optimizer,
        "asset": asset,
        "asset_class": asset_class,
        "frequency": "15min",
        "split": split,
        "gross_total_return": round(metrics.gross_total_return, 6),
        "net_total_return": round(metrics.net_total_return, 6),
        "total_return": round(metrics.net_total_return, 6),
        "annualized_return": round(metrics.annualized_return, 6),
        "annualized_volatility": round(metrics.annualized_volatility, 6),
        "gross_sharpe": round(metrics.gross_sharpe, 6),
        "net_sharpe": round(metrics.net_sharpe, 6),
        "sharpe": round(metrics.net_sharpe, 6),
        "sortino": round(metrics.sortino, 6),
        "max_drawdown": round(metrics.max_drawdown, 6),
        "calmar": round(metrics.calmar, 6),
        "hit_rate": round(metrics.hit_rate, 6),
        "turnover": round(metrics.turnover, 6),
        "total_transaction_cost": round(metrics.total_transaction_cost, 6),
        "trade_count": int(metrics.trade_count),
        "average_trade_pnl": round(metrics.average_trade_pnl, 6),
        "exposure_time": round(metrics.exposure_time, 6),
        "cost_bps": round(float(cost_bps), 6),
    }
    row["config_source"] = config_source
    return row


def _evaluate_candidates_on_validation(
    candidates: list[dict[str, Any]],
    strategy_cls: type,
    validation_daily: pd.DataFrame,
    validation_minute: pd.DataFrame,
    asset_class: str,
    cost_config: TransactionCostConfig,
    cache: EvaluationCache,
    strategy_label: str,
    asset: str,
    guard: RuntimeGuard,
) -> list[tuple[dict[str, Any], MetricBundle]]:
    evaluated: list[tuple[dict[str, Any], MetricBundle]] = []
    seen: set[str] = set()
    for params in candidates:
        encoded = params_to_json(params)
        if encoded in seen:
            continue
        seen.add(encoded)
        guard.check()
        _, metrics, _ = _evaluate_with_cache(
            cache=cache,
            strategy_label=strategy_label,
            asset=asset,
            split="validation",
            strategy_cls=strategy_cls,
            params=params,
            daily_data=validation_daily,
            minute_data=validation_minute,
            asset_class=asset_class,
            cost_config=cost_config,
        )
        evaluated.append((params, metrics))
    return evaluated


def _select_by_validation(candidates: list[tuple[dict[str, Any], MetricBundle]]) -> tuple[dict[str, Any], MetricBundle]:
    valid = [item for item in candidates if _valid_metric_bundle(item[1])]
    if valid:
        return max(valid, key=lambda item: (item[1].net_sharpe, item[1].net_total_return))
    return max(candidates, key=lambda item: item[1].net_sharpe)


def _select_validation_candidates(
    candidate_params: list[dict[str, Any]],
    search_rows: list[dict[str, object]],
    *,
    limit: int | None,
) -> list[dict[str, Any]]:
    if limit is None or limit <= 0:
        return candidate_params
    by_id = {int(row["candidate_id"]): row for row in search_rows}
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for index, params in enumerate(candidate_params, start=1):
        row = by_id.get(index)
        score = float(row["train_net_sharpe"]) if row is not None and row.get("valid") else -1e6
        ranked.append((score, index, params))
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, params in sorted(ranked, key=lambda item: (item[0], -item[1]), reverse=True):
        encoded = params_to_json(params)
        if encoded in seen:
            continue
        selected.append(params)
        seen.add(encoded)
        if len(selected) >= limit:
            break
    return selected


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
    cost_config: TransactionCostConfig,
    cache: EvaluationCache,
    guard: RuntimeGuard,
    progress: ProgressLogger,
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
            guard.check()
            candidate_id += 1
            normalized = np.clip(mean + sigma * epsilon, 0.0, 1.0)
            raw = bounds_low + normalized * ranges
            params = param_space.clip_and_round(raw.tolist())
            _, metrics, cached = _evaluate_with_cache(
                cache=cache,
                strategy_label=strategy_label,
                asset=asset,
                split="train",
                strategy_cls=strategy_cls,
                params=params,
                daily_data=daily_data,
                minute_data=minute_data,
                asset_class=asset_class,
                cost_config=cost_config,
            )
            valid = _valid_metric_bundle(metrics)
            reward = metrics.net_sharpe if valid else -1e6
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
                    cost_bps=cost_config.cost_bps_for(asset_class),
                    valid=valid,
                )
            )
            progress.candidate_done(
                strategy=strategy_label,
                asset=asset,
                optimizer=optimizer_label,
                iteration=iteration,
                candidate=candidate_id,
                cached=cached,
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
    cost_config: TransactionCostConfig,
    cache: EvaluationCache,
    guard: RuntimeGuard,
    progress: ProgressLogger,
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
                guard.check()
                candidate_id += 1
                vector = optimizer.ask()
                raw = bounds_low + np.clip(vector, 0.0, 1.0) * ranges
                params = param_space.clip_and_round(raw.tolist())
                _, metrics, cached = _evaluate_with_cache(
                    cache=cache,
                    strategy_label=strategy_label,
                    asset=asset,
                    split="train",
                    strategy_cls=strategy_cls,
                    params=params,
                    daily_data=daily_data,
                    minute_data=minute_data,
                    asset_class=asset_class,
                    cost_config=cost_config,
                )
                valid = _valid_metric_bundle(metrics)
                reward = metrics.net_sharpe if valid else -1e6
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
                        cost_bps=cost_config.cost_bps_for(asset_class),
                        valid=valid,
                    )
                )
                solutions.append((vector, -reward))
                progress.candidate_done(
                    strategy=strategy_label,
                    asset=asset,
                    optimizer=optimizer_label,
                    iteration=iteration,
                    candidate=candidate_id,
                    cached=cached,
                )
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
                guard.check()
                candidate_id += 1
                step = rng.multivariate_normal(np.zeros(param_space.dimension), covariance)
                vector = np.clip(mean + sigma * step, 0.0, 1.0)
                raw = bounds_low + vector * ranges
                params = param_space.clip_and_round(raw.tolist())
                _, metrics, cached = _evaluate_with_cache(
                    cache=cache,
                    strategy_label=strategy_label,
                    asset=asset,
                    split="train",
                    strategy_cls=strategy_cls,
                    params=params,
                    daily_data=daily_data,
                    minute_data=minute_data,
                    asset_class=asset_class,
                    cost_config=cost_config,
                )
                valid = _valid_metric_bundle(metrics)
                reward = metrics.net_sharpe if valid else -1e6
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
                        cost_bps=cost_config.cost_bps_for(asset_class),
                        valid=valid,
                    )
                )
                progress.candidate_done(
                    strategy=strategy_label,
                    asset=asset,
                    optimizer=optimizer_label,
                    iteration=iteration,
                    candidate=candidate_id,
                    cached=cached,
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
    cost_config: TransactionCostConfig = DEFAULT_COST_CONFIG,
    asset_sample: str = "all",
    max_assets: int | None = None,
    timeout_minutes: float | None = None,
    cache: EvaluationCache | None = None,
    guard: RuntimeGuard | None = None,
    progress: ProgressLogger | None = None,
    validation_candidates: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Run optimization for one strategy across selected 15-minute assets."""
    ensure_processed_data_ready()

    strategy_spec = config.spec
    strategy_cls = strategy_spec.factory
    param_space = PARAM_SPACES[config.strategy_key]
    search_rows: list[dict[str, object]] = []
    selected_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []
    verification_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []

    selected_assets = _discover_assets(
        assets,
        smoke,
        asset_sample=asset_sample,
        max_assets=max_assets,
    )
    if not selected_assets:
        raise ValueError("No 15-minute assets selected for optimization.")

    if smoke:
        max_iters = min(max_iters, 2)
        population = min(max(population, 2), 4)
    population = max(population, 4 if config.optimizer == "CMA-ES" else 2)
    if config.optimizer == "NES" and population % 2 != 0:
        population += 1
    cache = cache or EvaluationCache()
    guard = guard or RuntimeGuard(timeout_minutes)
    progress = progress or ProgressLogger(
        total_candidates=len(selected_assets) * max_iters * population,
        guard=guard,
    )

    print(
        "[optimization] "
        f"strategy={strategy_spec.label} optimizer={config.optimizer} "
        f"assets={len(selected_assets)} iterations={max_iters} population={population} "
        f"candidate_backtests={len(selected_assets) * max_iters * population}",
        flush=True,
    )

    for asset, asset_class in selected_assets:
        guard.check()
        split_data = _limit_split_history(
            load_optimization_splits(asset, asset_class),
            max_bars=5_000 if smoke else None,
        )
        train_daily, train_minute = split_data["train"]
        validation_daily, validation_minute = split_data["validation"]

        baseline_train_result, baseline_train_metrics, _ = _evaluate_with_cache(
            cache=cache,
            strategy_label=strategy_spec.label,
            asset=asset,
            split="train",
            strategy_cls=strategy_cls,
            params=strategy_spec.params,
            daily_data=train_daily,
            minute_data=train_minute,
            asset_class=asset_class,
            cost_config=cost_config,
        )
        baseline_validation_result, baseline_validation_metrics, _ = _evaluate_with_cache(
            cache=cache,
            strategy_label=strategy_spec.label,
            asset=asset,
            split="validation",
            strategy_cls=strategy_cls,
            params=strategy_spec.params,
            daily_data=validation_daily,
            minute_data=validation_minute,
            asset_class=asset_class,
            cost_config=cost_config,
        )
        verification_rows.extend(
            [
                _verification_row(
                    strategy=strategy_spec.label,
                    optimizer=config.optimizer,
                    asset=asset,
                    asset_class=asset_class,
                    split="train",
                    metrics=baseline_train_metrics,
                    config_source="baseline",
                    cost_bps=cost_config.cost_bps_for(asset_class),
                ),
                _verification_row(
                    strategy=strategy_spec.label,
                    optimizer=config.optimizer,
                    asset=asset,
                    asset_class=asset_class,
                    split="validation",
                    metrics=baseline_validation_metrics,
                    config_source="baseline",
                    cost_bps=cost_config.cost_bps_for(asset_class),
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
                cost_config=cost_config,
                cache=cache,
                guard=guard,
                progress=progress,
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
                cost_config=cost_config,
                cache=cache,
                guard=guard,
                progress=progress,
            )
        search_rows.extend(asset_search_rows)
        validation_pool = _select_validation_candidates(
            candidate_params,
            asset_search_rows,
            limit=validation_candidates,
        )
        evaluated_validation_candidates = _evaluate_candidates_on_validation(
            validation_pool,
            strategy_cls,
            validation_daily,
            validation_minute,
            asset_class,
            cost_config,
            cache,
            strategy_spec.label,
            asset,
            guard,
        )
        selected_params, selected_validation_metrics = _select_by_validation(evaluated_validation_candidates)
        optimized_train_result, optimized_train_metrics, _ = _evaluate_with_cache(
            cache=cache,
            strategy_label=strategy_spec.label,
            asset=asset,
            split="train",
            strategy_cls=strategy_cls,
            params=selected_params,
            daily_data=train_daily,
            minute_data=train_minute,
            asset_class=asset_class,
            cost_config=cost_config,
        )
        optimized_validation_result, optimized_validation_metrics, _ = _evaluate_with_cache(
            cache=cache,
            strategy_label=strategy_spec.label,
            asset=asset,
            split="validation",
            strategy_cls=strategy_cls,
            params=selected_params,
            daily_data=validation_daily,
            minute_data=validation_minute,
            asset_class=asset_class,
            cost_config=cost_config,
        )
        verification_rows.extend(
            [
                _verification_row(
                    strategy=strategy_spec.label,
                    optimizer=config.optimizer,
                    asset=asset,
                    asset_class=asset_class,
                    split="train",
                    metrics=optimized_train_metrics,
                    config_source="optimized",
                    cost_bps=cost_config.cost_bps_for(asset_class),
                ),
                _verification_row(
                    strategy=strategy_spec.label,
                    optimizer=config.optimizer,
                    asset=asset,
                    asset_class=asset_class,
                    split="validation",
                    metrics=optimized_validation_metrics,
                    config_source="optimized",
                    cost_bps=cost_config.cost_bps_for(asset_class),
                ),
            ]
        )
        for split_name, result in [
            ("train", optimized_train_result),
            ("validation", optimized_validation_result),
        ]:
            detail = result.equity_detail.copy()
            if detail.empty:
                continue
            detail["timestamp"] = pd.to_datetime(detail["timestamp"], utc=True)
            detail = detail.reset_index(drop=True)
            detail["bar_index"] = detail.index.astype(int)
            peak = detail["net_equity"].cummax()
            detail["drawdown"] = ((detail["net_equity"] / peak) - 1.0) * 100.0
            detail["strategy"] = strategy_spec.label
            detail["config_source"] = "optimized"
            detail["optimizer"] = config.optimizer
            detail["asset"] = asset
            detail["asset_class"] = asset_class
            detail["frequency"] = "15min"
            detail["split"] = split_name
            detail["cost_bps"] = float(cost_config.cost_bps_for(asset_class))
            detail["params_json"] = params_to_json(selected_params)
            detail["selected_by"] = "validation_net_sharpe"
            detail = detail.rename(columns={"net_return_pct": "net_return"})
            curve_rows.extend(
                detail[
                    [
                        "bar_index",
                        "timestamp",
                        "strategy",
                        "config_source",
                        "optimizer",
                        "asset",
                        "asset_class",
                        "frequency",
                        "split",
                        "gross_equity",
                        "net_equity",
                        "net_return",
                        "drawdown",
                        "turnover",
                        "transaction_cost",
                        "cumulative_transaction_cost",
                        "cost_bps",
                        "params_json",
                        "selected_by",
                    ]
                ].to_dict("records")
            )

        selected_rows.append(
            {
                "strategy": strategy_spec.label,
                "optimizer": config.optimizer,
                "asset": asset,
                "asset_class": asset_class,
                "frequency": "15min",
                "selected_by": "validation_net_sharpe",
                "params_json": params_to_json(selected_params),
                "train_gross_sharpe": round(optimized_train_metrics.gross_sharpe, 6),
                "train_net_sharpe": round(optimized_train_metrics.net_sharpe, 6),
                "validation_net_sharpe": round(selected_validation_metrics.net_sharpe, 6),
                "train_sharpe": round(optimized_train_metrics.net_sharpe, 6),
                "validation_sharpe": round(selected_validation_metrics.net_sharpe, 6),
                "train_gross_return": round(optimized_train_metrics.gross_total_return, 6),
                "train_net_return": round(optimized_train_metrics.net_total_return, 6),
                "validation_net_return": round(selected_validation_metrics.net_total_return, 6),
                "train_return": round(optimized_train_metrics.net_total_return, 6),
                "validation_return": round(selected_validation_metrics.net_total_return, 6),
                "train_max_drawdown": round(optimized_train_metrics.max_drawdown, 6),
                "validation_max_drawdown": round(selected_validation_metrics.max_drawdown, 6),
                "train_trade_count": int(optimized_train_metrics.trade_count),
                "validation_trade_count": int(selected_validation_metrics.trade_count),
                "train_total_cost": round(optimized_train_metrics.total_transaction_cost, 6),
                "validation_total_cost": round(selected_validation_metrics.total_transaction_cost, 6),
                "train_turnover": round(optimized_train_metrics.turnover, 6),
                "validation_turnover": round(selected_validation_metrics.turnover, 6),
                "cost_bps": round(float(cost_config.cost_bps_for(asset_class)), 6),
            }
        )

        comparison_rows.append(
            {
                "strategy": strategy_spec.label,
                "optimizer": config.optimizer,
                "asset": asset,
                "asset_class": asset_class,
                "baseline_train_net_sharpe": round(baseline_train_metrics.net_sharpe, 6),
                "optimized_train_net_sharpe": round(optimized_train_metrics.net_sharpe, 6),
                "baseline_validation_net_sharpe": round(baseline_validation_metrics.net_sharpe, 6),
                "optimized_validation_net_sharpe": round(optimized_validation_metrics.net_sharpe, 6),
                "baseline_train_sharpe": round(baseline_train_metrics.net_sharpe, 6),
                "optimized_train_sharpe": round(optimized_train_metrics.net_sharpe, 6),
                "baseline_validation_sharpe": round(baseline_validation_metrics.net_sharpe, 6),
                "optimized_validation_sharpe": round(optimized_validation_metrics.net_sharpe, 6),
                "baseline_train_return": round(baseline_train_metrics.net_total_return, 6),
                "optimized_train_return": round(optimized_train_metrics.net_total_return, 6),
                "baseline_validation_return": round(baseline_validation_metrics.net_total_return, 6),
                "optimized_validation_return": round(optimized_validation_metrics.net_total_return, 6),
                "baseline_validation_max_drawdown": round(
                    baseline_validation_metrics.max_drawdown, 6
                ),
                "optimized_validation_max_drawdown": round(
                    optimized_validation_metrics.max_drawdown, 6
                ),
                "improvement_validation_net_sharpe": round(
                    optimized_validation_metrics.net_sharpe - baseline_validation_metrics.net_sharpe,
                    6,
                ),
                "improvement_validation_sharpe": round(
                    optimized_validation_metrics.net_sharpe - baseline_validation_metrics.net_sharpe,
                    6,
                ),
                "total_cost_difference": round(
                    optimized_validation_metrics.total_transaction_cost
                    - baseline_validation_metrics.total_transaction_cost,
                    6,
                ),
                "cost_bps": round(float(cost_config.cost_bps_for(asset_class)), 6),
                "overfit_warning": overfit_warning(
                    baseline_validation_net_sharpe=baseline_validation_metrics.net_sharpe,
                    optimized_train_net_sharpe=optimized_train_metrics.net_sharpe,
                    optimized_validation_net_sharpe=optimized_validation_metrics.net_sharpe,
                ),
            }
        )

    return {
        "search_results": pd.DataFrame(search_rows),
        "selected_params": pd.DataFrame(selected_rows),
        "comparison": pd.DataFrame(comparison_rows),
        "verification": pd.DataFrame(verification_rows),
        "curves": pd.DataFrame(curve_rows),
    }
