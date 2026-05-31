"""Kelly criterion portfolio construction with rolling window and grid search.

Works with multi-asset Workstream C equity curves (equity_curves_our_strats.csv).
Each instrument is a (strategy, asset) pair identified by the column name
"Strategy / Name | ASSET" produced by equal_weight.load_equity_curves().

Key design: bar-level returns are first aggregated into per-trade returns before
Kelly statistics are computed. Each trade starts with a constant-cost bar
(transaction cost payment) followed by one or more price-return bars.
Treating individual bars as trades would distort win_rate and R.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from final_portfolio.equal_weight import (
    DEFAULT_EQUITY_CURVES,
    compute_metrics,
    equity_curve_from_returns,
    load_equity_curves,
)

_INITIAL_CAPITAL = 100_000.0
_KELLY_FRACTION = 0.5  # Half-Kelly: reduces aggressiveness, standard in practice


# ── Core Kelly formula ───────────────────────────────────────────────────────

def compute_kelly_weight(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Compute fractional Kelly allocation for one instrument.

    Formula:  f = W - (1 - W) / R
    where W = win rate, R = avg_win / |avg_loss|.

    Multiplied by _KELLY_FRACTION (0.5 = Half-Kelly).
    Clamped to [0, 1]: negative Kelly means negative expected values.
    """
    if avg_loss == 0 or avg_win == 0:
        return 0.0
    R = avg_win / abs(avg_loss)
    f = win_rate - (1 - win_rate) / R
    return float(np.clip(f * _KELLY_FRACTION, 0.0, 1.0))


# ── Trade extraction ─────────────────────────────────────────────────────────

def _detect_cost_bar_value(series: pd.Series) -> float | None:
    """Find the constant transaction-cost bar value in a return series.

    Each trade in the equity curves starts with a bar whose net_return equals
    the transaction cost (constant per instrument, applied at trade entry).
    These bars appear ~40-50% of the time and always have exactly the same value.

    Note: the transaction_cost column is non-zero on every bar (entry + holding
    costs), so it cannot be used as a trade-boundary signal. The constant
    net_return pattern is the reliable indicator of trade entry bars.

    Returns the detected cost value, or None if not detectable.
    """
    if len(series) < 10:
        return None

    # Mode of the series rounded to 6 decimal places
    rounded = series.round(6)
    vc = rounded.value_counts()
    if len(vc) == 0:
        return None

    mode_val = float(vc.index[0])
    mode_frac = vc.iloc[0] / len(series)

    # Cost bars should appear in at least 20% of active bars
    if mode_frac < 0.20:
        return None

    # Cost bars are always negative (transaction cost)
    if mode_val >= 0:
        return None

    return mode_val


def extract_per_trade_returns(series: pd.Series) -> pd.Series:
    """Aggregate consecutive bars into per-trade compounded returns.

    Each trade starts at a cost bar (constant transaction-cost value) and ends
    just before the next cost bar. Returns are compounded within each trade.

    Parameters
    ----------
    series : pd.Series
        Non-zero bar-level net returns for one instrument (already filtered
        to drop zero/NaN bars). Index must be datetime.

    Returns
    -------
    pd.Series of per-trade compounded returns, indexed by trade-end timestamp.
    Falls back to treating each bar as a trade if cost structure is unclear.
    """
    if len(series) < 2:
        return series.copy()

    cost_val = _detect_cost_bar_value(series)

    if cost_val is None:
        return series.copy()

    # Use relative + absolute tolerance to handle tiny floating-point drift
    tol = max(abs(cost_val) * 0.01, 1e-6)
    is_cost = abs(series - cost_val) < tol

    # Each cost bar starts a new trade; increment a trade counter at each one
    trade_id = is_cost.cumsum()

    # Bars before the very first cost bar belong to no identified trade → skip
    trade_id = trade_id[trade_id > 0]
    aligned = series.loc[trade_id.index]

    trades_ret: list[float] = []
    trades_ts: list[pd.Timestamp] = []

    for tid, group in aligned.groupby(trade_id):
        compounded = float((np.prod(1 + group.values / 100) - 1) * 100)
        trades_ret.append(compounded)
        trades_ts.append(group.index[-1])

    if not trades_ret:
        return pd.Series(dtype=float)

    return pd.Series(trades_ret, index=pd.DatetimeIndex(trades_ts))


# ── Kelly weight computation ─────────────────────────────────────────────────

def kelly_weights_from_bars(
    trade_bars: pd.DataFrame,
    instruments: list[str],
    lookback: int,
) -> dict[str, float]:
    """Compute Kelly weights from the most recent completed trades.

    Internally calls extract_per_trade_returns to aggregate bar-level returns
    into proper per-trade outcomes before computing win_rate and R.

    Parameters
    ----------
    trade_bars : pd.DataFrame
        Wide DataFrame (same format as load_equity_curves output) already
        filtered to bars BEFORE the current rebalancing timestamp.
    instruments : list[str]
        Column names to include (e.g. "Strategy0 / Baseline | AAPL").
    lookback : int
        Number of most recent *trades* (not bars) per instrument to use.

    Returns
    -------
    dict mapping instrument → normalized weight (all weights sum to 1).
    """
    raw = {}
    for inst in instruments:
        if inst not in trade_bars.columns:
            raw[inst] = 0.0
            continue

        series = trade_bars[inst].dropna()
        active = series[series != 0]

        if len(active) < 5:
            raw[inst] = 0.0
            continue

        # Aggregate bars into per-trade returns
        trades = extract_per_trade_returns(active)
        recent = trades.tail(lookback)

        if len(recent) < 20:
            # Too few completed trades for a reliable Kelly estimate
            raw[inst] = 0.0
            continue

        wins = recent[recent > 0]
        losses = recent[recent < 0]

        win_rate = len(wins) / len(recent)
        avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
        avg_loss = float(losses.mean()) if len(losses) > 0 else -1e-6

        raw[inst] = compute_kelly_weight(win_rate, avg_win, avg_loss)

    total = sum(raw.values())
    if total == 0:
        # All Kelly weights are zero → fall back to equal weight
        n = len(instruments)
        return {inst: 1.0 / n for inst in instruments}

    # Cap each instrument at 3× equal weight to prevent extreme concentration
    # from noisy Kelly estimates dominating the portfolio
    max_weight = 3.0 / len(instruments)
    raw = {inst: min(w / total, max_weight) for inst, w in raw.items()}

    # Re-normalize after capping
    capped_total = sum(raw.values())
    if capped_total == 0:
        n = len(instruments)
        return {inst: 1.0 / n for inst in instruments}

    return {inst: w / capped_total for inst, w in raw.items()}


# ── Portfolio simulation ─────────────────────────────────────────────────────

def run_kelly_portfolio(
    csv_path: Path = DEFAULT_EQUITY_CURVES,
    lookback: int = 50,
    rebalancing_days: int = 30,
    split: str = "train",
    initial_capital: float = _INITIAL_CAPITAL,
) -> tuple[pd.Series, dict, pd.DataFrame]:
    """Simulate a rolling Half-Kelly portfolio on multi-asset equity curves.

    At every rebalancing_days interval, recompute Kelly weights using the
    last `lookback` completed trades per instrument. Only data that occurred
    BEFORE the rebalancing timestamp is used — no lookahead.

    Parameters
    ----------
    csv_path : Path
        Path to equity_curves_our_strats.csv.
    lookback : int
        Number of recent completed trades per instrument for Kelly calculation.
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
        Summary metrics including lookback, rebalancing_days, split.
    weight_history : pd.DataFrame
        One row per rebalancing event showing weights at that point.
    """
    # Load the requested split for simulation
    returns_split = load_equity_curves(csv_path, split=split)
    instruments = list(returns_split.columns)

    # Load ALL past data (train always, plus earlier validation bars as we progress).
    # This ensures Kelly sees full history at the start of validation —
    # not just the few bars that have passed in the current split.
    if split == "validation":
        returns_train = load_equity_curves(csv_path, split="train")
    else:
        returns_train = pd.DataFrame(columns=returns_split.columns)

    # Start with equal weights before enough history accumulates
    current_weights = {inst: 1.0 / len(instruments) for inst in instruments}
    weight_history: list[dict] = []
    portfolio_returns: list[float] = []
    last_rebal: pd.Timestamp | None = None

    for i, (ts, row) in enumerate(returns_split.iterrows()):
        # Rebalance when enough calendar days have passed
        if last_rebal is None or (ts - last_rebal).days >= rebalancing_days:
            # Full history = all training bars + validation bars seen so far
            current_split_past = returns_split.iloc[:i]
            if len(returns_train) > 0:
                past = pd.concat([returns_train, current_split_past])
            else:
                past = current_split_past
            current_weights = kelly_weights_from_bars(past, instruments, lookback)
            weight_history.append({"timestamp": ts, **current_weights})
            last_rebal = ts

        # Weighted portfolio return at this bar (NaN → 0)
        bar = row.fillna(0)
        port_ret = sum(current_weights.get(inst, 0.0) * bar[inst] for inst in instruments)
        portfolio_returns.append(port_ret)

    returns_series = pd.Series(portfolio_returns, index=returns_split.index)
    equity = equity_curve_from_returns(returns_series, initial_capital)
    metrics = compute_metrics(equity, returns_series)
    metrics.update({"lookback": lookback, "rebalancing_days": rebalancing_days, "split": split})

    weight_df = (
        pd.DataFrame(weight_history).set_index("timestamp")
        if weight_history else pd.DataFrame()
    )
    return equity, metrics, weight_df


# ── Grid search ──────────────────────────────────────────────────────────────

def grid_search_kelly(
    csv_path: Path = DEFAULT_EQUITY_CURVES,
    lookback_values: list[int] | None = None,
    rebalancing_values: list[int] | None = None,
) -> pd.DataFrame:
    """Test all lookback × rebalancing combinations on train data.

    lookback is in trades (not bars). With ~2 bars per trade in this dataset,
    lookback=50 ≈ last 100 bars ≈ last 2-3 months of trading history.

    Returns a DataFrame of results sorted by Sharpe ratio (best first).
    Only train split is used — validation is reserved for final evaluation.
    """
    if lookback_values is None:
        lookback_values = [20, 50, 100, 200]
    if rebalancing_values is None:
        rebalancing_values = [5, 15, 30]

    rows = []
    total = len(lookback_values) * len(rebalancing_values)
    done = 0

    for lb in lookback_values:
        for rb in rebalancing_values:
            done += 1
            print(f"  [{done}/{total}] lookback={lb} trades, rebal={rb} days...")
            _, metrics, _ = run_kelly_portfolio(
                csv_path=csv_path,
                lookback=lb,
                rebalancing_days=rb,
                split="train",
            )
            rows.append(metrics)

    return pd.DataFrame(rows).sort_values("sharpe_ratio", ascending=False).reset_index(drop=True)


# ── Public alias used by __init__.py ─────────────────────────────────────────

def fractional_kelly_weight(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Public alias for compute_kelly_weight."""
    return compute_kelly_weight(win_rate, avg_win, avg_loss)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running Kelly grid search on train split...")
    results = grid_search_kelly()

    print("\nGrid search results (sorted by Sharpe):")
    print(results[["lookback", "rebalancing_days", "sharpe_ratio",
                   "total_return_pct", "max_drawdown_pct"]].to_string(index=False))

    best = results.iloc[0]
    lb, rb = int(best["lookback"]), int(best["rebalancing_days"])
    print(f"\nBest: lookback={lb} trades, rebalancing={rb} days | "
          f"Sharpe={best['sharpe_ratio']:.4f}, Return={best['total_return_pct']:.4f}%")

    print("\nEvaluating best params on validation split...")
    _, val_metrics, _ = run_kelly_portfolio(lookback=lb, rebalancing_days=rb, split="validation")
    print(f"Validation → Sharpe={val_metrics['sharpe_ratio']:.4f}, "
          f"Return={val_metrics['total_return_pct']:.4f}%, "
          f"Max DD={val_metrics['max_drawdown_pct']:.4f}%")
