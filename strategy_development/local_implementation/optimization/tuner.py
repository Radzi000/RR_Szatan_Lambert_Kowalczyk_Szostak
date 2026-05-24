"""CMA-ES based strategy parameter tuner.

Uses the ``cmaes`` library to optimize strategy hyperparameters by
maximizing a user-chosen objective (Sharpe ratio by default).

Example
-------
>>> from intraday_momentum.optimization import StrategyTuner, PARAM_SPACES
>>> from intraday_momentum.strategies.strategy0 import Strategy0
>>> from intraday_momentum.backtest.engine import BacktestEngine
>>> from intraday_momentum.data.provider import DataProvider
>>>
>>> provider = DataProvider()
>>> daily = provider.get_daily_data("2019-01-01", "2019-12-31")
>>> minute = provider.get_data("2019-01-01", "2019-12-31", interval="5m")
>>> tuner = StrategyTuner(
...     strategy_cls=Strategy0,
...     param_space=PARAM_SPACES["Strategy0"],
...     daily_data=daily,
...     minute_data=minute,
... )
>>> best_params, best_score = tuner.run(n_generations=20, population_size=12)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..backtest.engine import BacktestEngine
from ..strategies.base import BaseStrategy
from .param_spaces import ParamSpace

logger = logging.getLogger(__name__)


@dataclass
class TunerResult:
    """Result container for an optimization run.

    Attributes
    ----------
    best_params : dict[str, Any]
        Best parameter combination found.
    best_score : float
        Objective value for the best parameters.
    history : list[dict[str, Any]]
        Per-generation statistics (generation, best, mean, std).
    all_evaluations : list[tuple[dict[str, Any], float]]
        Every (params, score) pair evaluated during the search.
    """

    best_params: dict[str, Any] = field(default_factory=dict)
    best_score: float = float("-inf")
    history: list[dict[str, Any]] = field(default_factory=list)
    all_evaluations: list[tuple[dict[str, Any], float]] = field(default_factory=list)


class StrategyTuner:
    """Optimize strategy parameters using CMA-ES.

    Parameters
    ----------
    strategy_cls : type[BaseStrategy]
        Strategy class to instantiate with candidate parameters.
    param_space : ParamSpace
        Defines which parameters to tune and their bounds.
    daily_data : pd.DataFrame
        Daily OHLCV data for backtesting.
    minute_data : pd.DataFrame
        Minute-bar OHLCV data for backtesting.
    objective : str
        Metric to maximize. One of ``"sharpe"``, ``"total_return"``,
        ``"win_rate"``, ``"calmar"`` (return / max-drawdown).
    initial_capital : float
        Starting capital for the backtest engine.
    """

    SUPPORTED_OBJECTIVES = ("sharpe", "total_return", "win_rate", "calmar")

    def __init__(
        self,
        strategy_cls: type[BaseStrategy],
        param_space: ParamSpace,
        daily_data: pd.DataFrame,
        minute_data: pd.DataFrame,
        objective: str = "sharpe",
        initial_capital: float = 100_000.0,
    ) -> None:
        if objective not in self.SUPPORTED_OBJECTIVES:
            msg = f"Objective must be one of {self.SUPPORTED_OBJECTIVES}, got '{objective}'"
            raise ValueError(msg)

        self.strategy_cls = strategy_cls
        self.param_space = param_space
        self.daily_data = daily_data
        self.minute_data = minute_data
        self.objective = objective
        self.initial_capital = initial_capital

    # ----------------------------------------------------------
    # Objective evaluation
    # ----------------------------------------------------------

    def _evaluate(self, params: dict[str, Any]) -> float:
        """Run a single backtest and return the objective score.

        Parameters
        ----------
        params : dict[str, Any]
            Strategy constructor keyword arguments.

        Returns
        -------
        float
            Objective value (higher is better). Returns ``-1e6`` on
            any exception so that CMA-ES can gracefully skip bad
            candidates.
        """
        try:
            strategy = self.strategy_cls(**params)
            engine = BacktestEngine(initial_capital=self.initial_capital)
            result = engine.run(strategy, self.daily_data, self.minute_data)
            summary = result.summary()

            if self.objective == "sharpe":
                return summary.get("sharpe_ratio", -1e6)
            if self.objective == "total_return":
                return summary.get("total_return_pct", -1e6)
            if self.objective == "win_rate":
                return summary.get("win_rate", -1e6)
            if self.objective == "calmar":
                ret = summary.get("total_return_pct", 0.0)
                dd = abs(summary.get("max_drawdown_pct", 1.0))
                return ret / dd if dd > 1e-9 else -1e6
        except Exception:
            logger.warning("Evaluation failed for params %s", params, exc_info=True)
            return -1e6

        return -1e6  # pragma: no cover

    # ----------------------------------------------------------
    # Main optimisation loop
    # ----------------------------------------------------------

    def run(
        self,
        n_generations: int = 30,
        population_size: int | None = None,
        sigma0: float = 0.3,
        seed: int | None = 42,
    ) -> TunerResult:
        """Run the CMA-ES optimization.

        Parameters
        ----------
        n_generations : int
            Number of CMA-ES generations (iterations).
        population_size : int | None
            Samples per generation. ``None`` lets CMA-ES choose a
            sensible default based on dimensionality.
        sigma0 : float
            Initial step-size (fraction of parameter range).
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        TunerResult
            Best parameters, score, and per-generation history.
        """
        from cmaes import CMA

        # Normalise defaults into [0, 1] so CMA-ES operates in a
        # unit hypercube, then map back for evaluation.
        space = self.param_space
        bounds_low = np.array(space.bounds_low)
        bounds_high = np.array(space.bounds_high)
        ranges = bounds_high - bounds_low
        ranges[ranges < 1e-12] = 1.0  # avoid division by zero

        mean0 = (np.array(space.defaults) - bounds_low) / ranges
        mean0 = np.clip(mean0, 0.01, 0.99)

        cma_kwargs: dict[str, Any] = {
            "mean": mean0,
            "sigma": sigma0,
            "bounds": np.column_stack([np.zeros(space.dimension), np.ones(space.dimension)]),
            "seed": seed,
        }
        if population_size is not None:
            cma_kwargs["population_size"] = population_size

        optimizer = CMA(**cma_kwargs)

        result = TunerResult()

        for gen in range(n_generations):
            solutions: list[tuple[np.ndarray, float]] = []
            pop_size = optimizer.population_size

            for _ in range(pop_size):
                x = optimizer.ask()
                # Map [0,1] back to real parameter ranges
                raw = bounds_low + x * ranges
                params = space.clip_and_round(raw.tolist())
                score = self._evaluate(params)

                result.all_evaluations.append((params, score))
                # CMA-ES minimises, so negate score
                solutions.append((x, -score))

                if score > result.best_score:
                    result.best_score = score
                    result.best_params = params

            optimizer.tell(solutions)

            gen_scores = [-s for _, s in solutions]
            gen_stats = {
                "generation": gen,
                "best": max(gen_scores),
                "mean": float(np.mean(gen_scores)),
                "std": float(np.std(gen_scores)),
                "cumulative_best": result.best_score,
            }
            result.history.append(gen_stats)

            logger.info(
                "Gen %d/%d  best=%.4f  mean=%.4f  cumul_best=%.4f",
                gen + 1,
                n_generations,
                gen_stats["best"],
                gen_stats["mean"],
                result.best_score,
            )

        logger.info("Optimization complete. Best score=%.4f", result.best_score)
        logger.info("Best params: %s", result.best_params)
        return result
