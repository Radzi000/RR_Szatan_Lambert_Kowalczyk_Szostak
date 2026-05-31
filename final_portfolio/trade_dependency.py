"""Trade dependency analysis and weight adjustment for Kelly and Markowitz portfolios.

Theory:
    If consecutive trade outcomes for an instrument are positively autocorrelated
    (lag-1 ACF > 0), the instrument exhibits *momentum*: wins tend to follow wins.
    Negative autocorrelation indicates *mean-reversion*: a win is typically followed
    by a loss.

    We exploit this by adjusting base portfolio weights at each rebalancing step:

        multiplier_i = 1 + alpha * ACF_i * sign(last_trade_i)

    where:
        ACF_i      = lag-1 autocorrelation of instrument i (estimated on training data)
        last_trade_i = return of the most recently completed trade for instrument i
        alpha      = sensitivity parameter (default 0.3, Half-Kelly style)

    After applying multipliers we re-normalize so weights still sum to 1.
    The multiplier is clamped to [0, 2] to prevent extreme adjustments.
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
from final_portfolio.kelly import (
    extract_per_trade_returns,
    kelly_weights_from_bars,
)


# ── Autocorrelation analysis ──────────────────────────────────────────────────

def compute_trade_autocorrelations(
    csv_path: Path = DEFAULT_EQUITY_CURVES,
    split: str = "train",
    max_lag: int = 3,
) -> pd.DataFrame:
    """Compute per-instrument trade autocorrelation from historical data.

    Each instrument's bar-level returns are first aggregated into per-trade
    returns (using Kelly's extract_per_trade_returns), then the autocorrelation
    function (ACF) is computed at each lag.

    Parameters
    ----------
    csv_path : Path
        Path to equity_curves_our_strats.csv.
    split : str
        Which data split to use for estimation ("train" recommended).
    max_lag : int
        Number of lags to compute.

    Returns
    -------
    pd.DataFrame with columns: instrument, n_trades, win_rate,
        lag1_acf, lag2_acf, ..., interpretation.
    """
    returns = load_equity_curves(csv_path, split=split)
    rows = []

    for inst in returns.columns:
        series = returns[inst].dropna()
        active = series[series != 0]
        trades = extract_per_trade_returns(active)

        if len(trades) < 20:
            continue

        wins = (trades > 0).sum()
        n = len(trades)
        row: dict = {
            "instrument": inst,
            "n_trades": n,
            "win_rate": round(wins / n, 4),
        }

        for lag in range(1, max_lag + 1):
            acf = trades.autocorr(lag=lag)
            row[f"lag{lag}_acf"] = round(float(acf) if not pd.isna(acf) else 0.0, 4)

        lag1 = row.get("lag1_acf", 0.0)
        if lag1 > 0.05:
            row["interpretation"] = "momentum"
        elif lag1 < -0.05:
            row["interpretation"] = "mean_reversion"
        else:
            row["interpretation"] = "independent"

        rows.append(row)

    return pd.DataFrame(rows)


def estimate_instrument_acf(
    past: pd.DataFrame,
    instruments: list[str],
    lag: int = 1,
) -> dict[str, float]:
    """Estimate lag-`lag` autocorrelation per instrument from `past` data.

    Parameters
    ----------
    past : pd.DataFrame
        Wide DataFrame of bar-level returns (all history up to current ts).
    instruments : list[str]
        Instrument column names.
    lag : int
        Autocorrelation lag.

    Returns
    -------
    dict mapping instrument → lag-N autocorrelation (0.0 if insufficient data).
    """
    acf_map: dict[str, float] = {}
    for inst in instruments:
        if inst not in past.columns:
            acf_map[inst] = 0.0
            continue
        series = past[inst].dropna()
        active = series[series != 0]
        trades = extract_per_trade_returns(active)
        if len(trades) < 20:
            acf_map[inst] = 0.0
            continue
        val = trades.autocorr(lag=lag)
        acf_map[inst] = float(val) if not pd.isna(val) else 0.0
    return acf_map


def last_trade_signs(
    past: pd.DataFrame,
    instruments: list[str],
) -> dict[str, float]:
    """Return the sign of the most recent completed trade per instrument.

    Returns +1 (last trade was a win), -1 (loss), or 0 (no history).
    """
    signs: dict[str, float] = {}
    for inst in instruments:
        if inst not in past.columns:
            signs[inst] = 0.0
            continue
        series = past[inst].dropna()
        active = series[series != 0]
        trades = extract_per_trade_returns(active)
        if len(trades) == 0:
            signs[inst] = 0.0
        else:
            signs[inst] = float(np.sign(trades.iloc[-1]))
    return signs


# ── Weight adjustment ─────────────────────────────────────────────────────────

def apply_dependency_adjustment(
    base_weights: dict[str, float],
    acf_map: dict[str, float],
    last_signs: dict[str, float],
    alpha: float = 0.3,
) -> dict[str, float]:
    """Adjust portfolio weights based on trade autocorrelation and last outcome.

    For each instrument:
        multiplier = clip(1 + alpha * ACF * sign(last_trade), 0, 2)

    Intuition:
        Momentum  + last win  → multiplier > 1 → increase weight
        Momentum  + last loss → multiplier < 1 → decrease weight
        MeanRev   + last win  → multiplier < 1 → decrease weight
        MeanRev   + last loss → multiplier > 1 → increase weight
        Independent           → multiplier ≈ 1 → no change

    Parameters
    ----------
    base_weights : dict[str, float]
        Weights from Kelly or Markowitz (sum to 1).
    acf_map : dict[str, float]
        Lag-1 autocorrelation per instrument.
    last_signs : dict[str, float]
        Sign of last trade per instrument (+1, -1, or 0).
    alpha : float
        Sensitivity (0 = no adjustment, 1 = full).

    Returns
    -------
    dict of adjusted weights (re-normalized to sum to 1).
    """
    adjusted: dict[str, float] = {}
    for inst, w in base_weights.items():
        acf = acf_map.get(inst, 0.0)
        sign = last_signs.get(inst, 0.0)
        multiplier = float(np.clip(1.0 + alpha * acf * sign, 0.0, 2.0))
        adjusted[inst] = w * multiplier

    total = sum(adjusted.values())
    if total < 1e-10:
        n = len(base_weights)
        return {inst: 1.0 / n for inst in base_weights}

    return {inst: w / total for inst, w in adjusted.items()}


# ── Portfolio run with dependency adjustment ──────────────────────────────────

def run_kelly_with_dependency(
    csv_path: Path = DEFAULT_EQUITY_CURVES,
    lookback: int = 50,
    rebalancing_days: int = 30,
    split: str = "validation",
    alpha: float = 0.3,
    initial_capital: float = 100_000.0,
) -> tuple[pd.Series, dict, pd.DataFrame]:
    """Run Kelly portfolio with trade-dependency weight adjustment.

    At each rebalancing step:
    1. Compute Kelly weights from recent trade history (base weights).
    2. Estimate lag-1 ACF per instrument from all available history.
    3. Apply dependency multipliers to base weights and re-normalize.

    Parameters match run_kelly_portfolio, plus:
        alpha : float
            Sensitivity of dependency adjustment (default 0.3 = Half-Kelly style).
    """
    from final_portfolio.kelly import _INITIAL_CAPITAL

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
            past = (
                pd.concat([returns_train, current_split_past])
                if len(returns_train) > 0 else current_split_past
            )

            # Step 1: base Kelly weights
            base_weights = kelly_weights_from_bars(past, instruments, lookback)

            # Step 2: trade dependency signals
            acf_map = estimate_instrument_acf(past, instruments)
            signs = last_trade_signs(past, instruments)

            # Step 3: dependency-adjusted weights
            current_weights = apply_dependency_adjustment(
                base_weights, acf_map, signs, alpha=alpha
            )

            weight_history.append({"timestamp": ts, **current_weights})
            last_rebal = ts

        bar = row.fillna(0)
        port_ret = sum(current_weights.get(inst, 0.0) * bar[inst] for inst in instruments)
        portfolio_returns.append(port_ret)

    returns_series = pd.Series(portfolio_returns, index=returns_split.index)
    equity = equity_curve_from_returns(returns_series, initial_capital)
    metrics = compute_metrics(equity, returns_series)
    metrics.update({
        "lookback": lookback,
        "rebalancing_days": rebalancing_days,
        "alpha": alpha,
        "split": split,
        "method": "kelly_dependency",
    })

    weight_df = (
        pd.DataFrame(weight_history).set_index("timestamp")
        if weight_history else pd.DataFrame()
    )
    return equity, metrics, weight_df


def run_markowitz_with_dependency(
    csv_path: Path = DEFAULT_EQUITY_CURVES,
    lookback_days: int = 90,
    rebalancing_days: int = 30,
    split: str = "validation",
    alpha: float = 0.3,
    initial_capital: float = 100_000.0,
) -> tuple[pd.Series, dict, pd.DataFrame]:
    """Run Markowitz portfolio with trade-dependency weight adjustment.

    Same structure as run_kelly_with_dependency but uses MVO as the base.
    """
    from final_portfolio.markowitz import mvo_weights_from_window

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
            past = (
                pd.concat([returns_train, current_split_past])
                if len(returns_train) > 0 else current_split_past
            )

            # Step 1: base MVO weights from calendar-day window
            window_start = ts - pd.Timedelta(days=lookback_days)
            window = past[past.index >= window_start]
            base_weights = mvo_weights_from_window(window, instruments)

            # Step 2: trade dependency signals (use full past, not just window)
            acf_map = estimate_instrument_acf(past, instruments)
            signs = last_trade_signs(past, instruments)

            # Step 3: dependency-adjusted weights
            current_weights = apply_dependency_adjustment(
                base_weights, acf_map, signs, alpha=alpha
            )

            weight_history.append({"timestamp": ts, **current_weights})
            last_rebal = ts

        bar = row.fillna(0)
        port_ret = sum(current_weights.get(inst, 0.0) * bar[inst] for inst in instruments)
        portfolio_returns.append(port_ret)

    returns_series = pd.Series(portfolio_returns, index=returns_split.index)
    equity = equity_curve_from_returns(returns_series, initial_capital)
    metrics = compute_metrics(equity, returns_series)
    metrics.update({
        "lookback_days": lookback_days,
        "rebalancing_days": rebalancing_days,
        "alpha": alpha,
        "split": split,
        "method": "markowitz_dependency",
    })

    weight_df = (
        pd.DataFrame(weight_history).set_index("timestamp")
        if weight_history else pd.DataFrame()
    )
    return equity, metrics, weight_df


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from final_portfolio.kelly import run_kelly_portfolio
    from final_portfolio.markowitz import run_markowitz_portfolio

    KELLY_LB, KELLY_RB = 50, 30   # example values — run run_report.py for grid-search-selected params
    MVO_LB, MVO_RB = 90, 30

    print("=== Trade Dependency Analysis (train split) ===\n")
    acf_df = compute_trade_autocorrelations(split="train")
    print(acf_df[["instrument", "n_trades", "win_rate", "lag1_acf", "interpretation"]].to_string(index=False))
    print()
    print("Interpretation breakdown:")
    print(acf_df["interpretation"].value_counts().to_string())

    print("\n=== Impact of dependency adjustment on VALIDATION ===\n")

    # Baseline Kelly
    _, km_v, _ = run_kelly_portfolio(
        lookback=KELLY_LB, rebalancing_days=KELLY_RB, split="validation"
    )
    # Kelly + dependency
    _, kd_v, _ = run_kelly_with_dependency(
        lookback=KELLY_LB, rebalancing_days=KELLY_RB, split="validation"
    )

    # Baseline Markowitz
    _, mm_v, _ = run_markowitz_portfolio(
        lookback_days=MVO_LB, rebalancing_days=MVO_RB, split="validation"
    )
    # Markowitz + dependency
    _, md_v, _ = run_markowitz_with_dependency(
        lookback_days=MVO_LB, rebalancing_days=MVO_RB, split="validation"
    )

    print(f"{'Method':<40} {'Sharpe':>8} {'Return':>10} {'MaxDD':>10}")
    print("-" * 72)
    for label, m in [
        ("Kelly (baseline)",            km_v),
        ("Kelly + dependency adj.",     kd_v),
        ("Markowitz (baseline)",        mm_v),
        ("Markowitz + dependency adj.", md_v),
    ]:
        print(f"{label:<40} {m['sharpe_ratio']:>8.4f} {m['total_return_pct']:>+10.2f}% {m['max_drawdown_pct']:>+10.2f}%")
