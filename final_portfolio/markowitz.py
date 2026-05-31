"""Markowitz mean-variance portfolio construction with rolling window and grid search.

Works with the same multi-asset equity curves as equal_weight.py and kelly.py.

At each rebalancing point the algorithm:
1. Takes a time window of the last `lookback_days` calendar days of bar-level returns.
2. Computes the sample mean return vector and covariance matrix (NaN = instrument flat → 0).
3. Solves for the maximum-Sharpe portfolio subject to weights ≥ 0, sum = 1.
4. Applies a 3× equal-weight cap per instrument to prevent extreme concentration.

Using calendar-day lookback (not row count) ensures equities and crypto instruments
are evaluated over the same time horizon regardless of their bar frequency.

The optimizer used is scipy.optimize.minimize with SLSQP (sequential least squares).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from final_portfolio.equal_weight import (
    DEFAULT_EQUITY_CURVES,
    compute_metrics,
    equity_curve_from_returns,
    load_equity_curves,
)

_INITIAL_CAPITAL = 100_000.0
_MIN_ACTIVE_BARS = 20  # minimum non-zero bars per instrument in window


# ── Core MVO solver ──────────────────────────────────────────────────────────

def max_sharpe_weights(
    returns_window: pd.DataFrame,
    max_weight: float = 1.0,
) -> np.ndarray:
    """Solve for the maximum-Sharpe portfolio weights using SLSQP.

    Parameters
    ----------
    returns_window : pd.DataFrame
        Wide DataFrame of bar-level returns (rows = bars, columns = instruments).
        NaN → 0 (instrument flat at that bar).
    max_weight : float
        Upper bound on any single instrument's weight (1.0 = unconstrained).

    Returns
    -------
    np.ndarray of weights that sum to 1, shape (n_instruments,).
    Falls back to equal weight if optimization fails or is degenerate.
    """
    R = returns_window.fillna(0).values  # shape (T, N)
    N = R.shape[1]

    if N == 0:
        return np.array([])

    mu = R.mean(axis=0)
    cov = np.cov(R, rowvar=False) if R.shape[0] > 1 else np.eye(N) * 1e-6

    # Regularize: prevents singular matrix when instruments are highly correlated
    cov += np.eye(N) * 1e-8

    def neg_sharpe(w: np.ndarray) -> float:
        port_ret = w @ mu
        port_std = np.sqrt(max(w @ cov @ w, 0.0))
        if port_std < 1e-10:
            return 0.0
        return -(port_ret / port_std)

    w0 = np.ones(N) / N  # start from equal weight
    bounds = [(0.0, max_weight)] * N
    constraints = {"type": "eq", "fun": lambda w: w.sum() - 1.0}

    result = minimize(
        neg_sharpe,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 500},
    )

    if not result.success or np.any(np.isnan(result.x)):
        return w0  # fall back to equal weight on solver failure

    w = np.clip(result.x, 0.0, None)
    total = w.sum()
    if total < 1e-10:
        return w0
    return w / total


# ── Rolling MVO weights ───────────────────────────────────────────────────────

def mvo_weights_from_window(
    window: pd.DataFrame,
    instruments: list[str],
) -> dict[str, float]:
    """Compute Markowitz max-Sharpe weights from a pre-sliced time window.

    Parameters
    ----------
    window : pd.DataFrame
        Wide DataFrame already sliced to the desired lookback period.
        Rows = timestamps, columns = instruments, values = net_return (NaN if flat).
    instruments : list[str]
        Full list of instruments (defines the weight vector's length).

    Returns
    -------
    dict mapping instrument → weight (all weights sum to 1).
    """
    n_all = len(instruments)
    fallback = {inst: 1.0 / n_all for inst in instruments}

    available = [c for c in instruments if c in window.columns]
    if len(available) < 2:
        return fallback

    # Keep only instruments with enough non-zero activity in the window
    active_cols = [
        c for c in available
        if (window[c].notna() & (window[c] != 0)).sum() >= _MIN_ACTIVE_BARS
    ]

    if len(active_cols) < 2:
        return fallback

    # Cap weight per instrument at 3× equal weight to prevent extreme concentration
    max_w = 3.0 / n_all
    w_arr = max_sharpe_weights(window[active_cols], max_weight=max_w)

    weight_map = {inst: 0.0 for inst in instruments}
    for col, w in zip(active_cols, w_arr):
        weight_map[col] = float(w)

    total = sum(weight_map.values())
    if total < 1e-10:
        return fallback

    return {inst: w / total for inst, w in weight_map.items()}


# ── Portfolio simulation ──────────────────────────────────────────────────────

def run_markowitz_portfolio(
    csv_path: Path = DEFAULT_EQUITY_CURVES,
    lookback_days: int = 90,
    rebalancing_days: int = 30,
    split: str = "train",
    initial_capital: float = _INITIAL_CAPITAL,
) -> tuple[pd.Series, dict, pd.DataFrame]:
    """Simulate a rolling Markowitz max-Sharpe portfolio.

    At every rebalancing_days interval, recompute MVO weights using the last
    `lookback_days` calendar days of data. No lookahead: only data before the
    rebalancing timestamp is used.

    Using calendar-day lookback ensures equities (sparse bars) and crypto
    (dense bars) are evaluated over the same time horizon.

    Parameters
    ----------
    csv_path : Path
        Path to equity_curves_our_strats.csv.
    lookback_days : int
        Number of calendar days to include in the mean/covariance window.
    rebalancing_days : int
        How often (in calendar days) to recompute weights.
    split : str
        "train" or "validation".
    initial_capital : float
        Starting capital in dollars.

    Returns
    -------
    equity : pd.Series
        Portfolio equity curve.
    metrics : dict
        Summary metrics including lookback_days, rebalancing_days, split.
    weight_history : pd.DataFrame
        One row per rebalancing event showing weights at that point.
    """
    returns_split = load_equity_curves(csv_path, split=split)
    instruments = list(returns_split.columns)

    if split == "validation":
        returns_train = load_equity_curves(csv_path, split="train")
    else:
        returns_train = pd.DataFrame(columns=returns_split.columns)

    current_weights = {inst: 1.0 / len(instruments) for inst in instruments}
    weight_history: list[dict] = []
    portfolio_returns: list[float] = []
    last_rebal: pd.Timestamp | None = None

    for i, (ts, row) in enumerate(returns_split.iterrows()):
        if last_rebal is None or (ts - last_rebal).days >= rebalancing_days:
            current_split_past = returns_split.iloc[:i]
            if len(returns_train) > 0:
                past = pd.concat([returns_train, current_split_past])
            else:
                past = current_split_past

            # Slice to the last lookback_days calendar days
            window_start = ts - pd.Timedelta(days=lookback_days)
            window = past[past.index >= window_start]

            current_weights = mvo_weights_from_window(window, instruments)
            weight_history.append({"timestamp": ts, **current_weights})
            last_rebal = ts

        bar = row.fillna(0)
        port_ret = sum(current_weights.get(inst, 0.0) * bar[inst] for inst in instruments)
        portfolio_returns.append(port_ret)

    returns_series = pd.Series(portfolio_returns, index=returns_split.index)
    equity = equity_curve_from_returns(returns_series, initial_capital)
    metrics = compute_metrics(equity, returns_series)
    metrics.update({"lookback_days": lookback_days, "rebalancing_days": rebalancing_days, "split": split})

    weight_df = (
        pd.DataFrame(weight_history).set_index("timestamp")
        if weight_history else pd.DataFrame()
    )
    return equity, metrics, weight_df


# ── Grid search ───────────────────────────────────────────────────────────────

def grid_search_markowitz(
    csv_path: Path = DEFAULT_EQUITY_CURVES,
    lookback_values: list[int] | None = None,
    rebalancing_values: list[int] | None = None,
) -> pd.DataFrame:
    """Test all lookback_days × rebalancing combinations on train data.

    lookback_values are in calendar days (e.g. 90 = last 3 months of data).

    Returns a DataFrame sorted by Sharpe ratio (best first).
    Only train split is used — validation is reserved for final evaluation.
    """
    if lookback_values is None:
        lookback_values = [60, 90, 180, 365]
    if rebalancing_values is None:
        rebalancing_values = [5, 15, 30]

    rows = []
    total = len(lookback_values) * len(rebalancing_values)
    done = 0

    for lb in lookback_values:
        for rb in rebalancing_values:
            done += 1
            print(f"  [{done}/{total}] lookback={lb} days, rebal={rb} days...")
            _, metrics, _ = run_markowitz_portfolio(
                csv_path=csv_path,
                lookback_days=lb,
                rebalancing_days=rb,
                split="train",
            )
            rows.append(metrics)

    return pd.DataFrame(rows).sort_values("sharpe_ratio", ascending=False).reset_index(drop=True)


# ── Public helper ─────────────────────────────────────────────────────────────

def normalize_weights(weights: np.ndarray) -> np.ndarray:
    """Normalize a weight array to sum to 1."""
    total = weights.sum()
    if total == 0:
        return np.ones(len(weights)) / len(weights)
    return weights / total


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running Markowitz grid search on train split...")
    results = grid_search_markowitz()

    print("\nGrid search results (sorted by Sharpe):")
    print(results[["lookback_days", "rebalancing_days", "sharpe_ratio",
                   "total_return_pct", "max_drawdown_pct"]].to_string(index=False))

    best = results.iloc[0]
    lb, rb = int(best["lookback_days"]), int(best["rebalancing_days"])
    print(f"\nBest: lookback={lb} days, rebalancing={rb} days | "
          f"Sharpe={best['sharpe_ratio']:.4f}, Return={best['total_return_pct']:.4f}%")

    print("\nEvaluating best params on validation split...")
    _, val_metrics, _ = run_markowitz_portfolio(
        lookback_days=lb, rebalancing_days=rb, split="validation"
    )
    print(f"Validation → Sharpe={val_metrics['sharpe_ratio']:.4f}, "
          f"Return={val_metrics['total_return_pct']:.4f}%, "
          f"Max DD={val_metrics['max_drawdown_pct']:.4f}%")
