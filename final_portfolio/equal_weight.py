"""Equal-weight portfolio construction from multi-asset strategy equity curves."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Workstream C equity curves: 5 strategies x 7 assets, parameters tuned via grid search/NES/CMA-ES
DEFAULT_EQUITY_CURVES = (
    Path(__file__).resolve().parents[1]
    / "outputs/tables/equity_curves_our_strats.csv"
)


def load_equity_curves(csv_path: Path, split: str = "train") -> pd.DataFrame:
    """Load multi-asset equity curves and return a wide DataFrame.

    Each column represents one (strategy, asset) combination.
    Rows = timestamps, values = net_return at that bar.

    Parameters
    ----------
    csv_path : Path
        Path to equity_curves_our_strats.csv (Workstream C output).
    split : str
        "train", "validation", or "test". Filters rows to the requested split only.

    Returns
    -------
    Wide DataFrame indexed by timestamp.
    Columns are strings like "Strategy0 / Baseline | AAPL".
    """
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    if split not in ("train", "validation", "test"):
        raise ValueError(f"Unknown split: '{split}'. Use 'train' or 'validation'.")

    df = df[df["split"] == split].copy()

    # Build a combined column key: "StrategyName | Asset"
    df["instrument"] = df["strategy"] + " | " + df["asset"]

    wide = df.pivot_table(
        index="timestamp",
        columns="instrument",
        values="net_return",
        aggfunc="first",
    )
    wide.columns.name = None
    return wide.sort_index()


def bars_per_year(returns: pd.DataFrame) -> float:
    """Estimate annualization factor from the actual data time span.

    Avoids hardcoding 5-min vs 15-min assumptions by computing
    bars_per_year = total_bars / total_years from the index.
    """
    if len(returns) < 2:
        raise ValueError("Need at least 2 bars to estimate annualization factor.")
    total_days = (returns.index[-1] - returns.index[0]).days
    total_years = max(total_days / 365.25, 0.01)
    return len(returns) / total_years


def equal_weight_returns(returns: pd.DataFrame) -> pd.Series:
    """Compute equal-weight portfolio return at each bar.

    Each (strategy, asset) instrument gets weight 1/N.
    NaN = instrument not trading at this bar → contributes 0 return.
    """
    return returns.fillna(0).mean(axis=1)


def equity_curve_from_returns(
    returns: pd.Series,
    initial_capital: float = 100_000.0,
) -> pd.Series:
    """Build an equity curve from a series of percentage returns.

    Compounds bar by bar starting from initial_capital.
    Example: -1% bar → multiplier 0.99, +2% bar → multiplier 1.02.
    """
    multipliers = 1 + returns / 100
    return initial_capital * multipliers.cumprod()


def compute_metrics(equity: pd.Series, returns: pd.DataFrame | pd.Series) -> dict:
    """Compute key portfolio metrics.

    Parameters
    ----------
    equity : pd.Series
        Portfolio equity curve.
    returns : pd.Series or pd.DataFrame
        Bar-by-bar returns used for Sharpe calculation.
        If DataFrame, the equal-weight mean is used.

    Returns
    -------
    dict with: total_return_pct, sharpe_ratio, max_drawdown_pct, num_bars
    """
    total_return = (equity.iloc[-1] / equity.iloc[0] - 1) * 100

    # Use the 1D return series for Sharpe
    ret_series = returns if isinstance(returns, pd.Series) else returns.fillna(0).mean(axis=1)

    mean_ret = ret_series.mean()
    std_ret = ret_series.std()
    bpy = bars_per_year(equity.to_frame())
    sharpe = (mean_ret / std_ret * np.sqrt(bpy)) if std_ret > 0 else 0.0

    # Max drawdown: largest peak-to-trough decline in %
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak * 100
    max_drawdown = drawdown.min()

    return {
        "total_return_pct": round(total_return, 4),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown_pct": round(max_drawdown, 4),
        "num_bars": len(ret_series),
    }


def equal_weight_vector(n: int) -> list[float]:
    """Return an equal-weight vector of length n.

    Example: n=5 → [0.2, 0.2, 0.2, 0.2, 0.2]
    """
    return [1.0 / n] * n


def run_equal_weight(
    csv_path: Path = DEFAULT_EQUITY_CURVES,
    split: str = "train",
    initial_capital: float = 100_000.0,
) -> tuple[pd.Series, dict]:
    """Run the full equal-weight portfolio pipeline.

    Parameters
    ----------
    csv_path : Path
        Path to equity_curves_our_strats.csv.
    split : str
        "train" or "validation".
    initial_capital : float
        Starting capital in dollars.

    Returns
    -------
    equity : pd.Series
        Portfolio equity curve.
    metrics : dict
        Summary metrics (total return, Sharpe, max drawdown).
    """
    returns_wide = load_equity_curves(csv_path, split=split)
    portfolio_returns = equal_weight_returns(returns_wide)
    equity = equity_curve_from_returns(portfolio_returns, initial_capital)
    metrics = compute_metrics(equity, portfolio_returns)
    metrics["split"] = split
    metrics["n_instruments"] = len(returns_wide.columns)
    return equity, metrics


if __name__ == "__main__":
    print("=== Equal-weight portfolio (train) ===")
    equity_train, metrics_train = run_equal_weight(split="train")
    print(f"Instruments : {metrics_train['n_instruments']}")
    print(f"Total return: {metrics_train['total_return_pct']}%")
    print(f"Sharpe ratio: {metrics_train['sharpe_ratio']}")
    print(f"Max drawdown: {metrics_train['max_drawdown_pct']}%")

    print("\n=== Equal-weight portfolio (validation) ===")
    equity_val, metrics_val = run_equal_weight(split="validation")
    print(f"Instruments : {metrics_val['n_instruments']}")
    print(f"Total return: {metrics_val['total_return_pct']}%")
    print(f"Sharpe ratio: {metrics_val['sharpe_ratio']}")
    print(f"Max drawdown: {metrics_val['max_drawdown_pct']}%")
