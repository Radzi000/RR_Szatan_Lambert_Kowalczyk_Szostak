"""Run fixed-parameter 15-minute cross-asset baseline experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from preprocessing import discover_data_files, materialize_processed_data
from preprocessing.loader import load_all_splits

from .backtest.engine import BacktestEngine, BacktestResult
from .costs import DEFAULT_COST_CONFIG, TransactionCostConfig, add_cost_args, cost_config_from_args
from .reproduce import PROJECT_ROOT
from .strategy_specs import STRATEGY_SPECS

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
TABLE_NAMES = {
    "summary": "fixed_15m_strategy_summary.csv",
    "returns": "fixed_15m_strategy_returns.csv",
    "trades": "fixed_15m_trade_logs.csv",
    "split_summary": "fixed_15m_train_validation_test_summary.csv",
}
RETURN_COLUMNS = [
    "asset",
    "asset_class",
    "strategy",
    "split",
    "timestamp",
    "gross_equity",
    "net_equity",
    "gross_return_pct",
    "net_return_pct",
    "turnover",
    "transaction_cost",
    "cumulative_transaction_cost",
]
TRADE_COLUMNS = [
    "asset",
    "asset_class",
    "strategy",
    "split",
    "trade_id",
    "entry_time",
    "exit_time",
    "direction",
    "entry_price",
    "exit_price",
    "leverage",
    "gross_pnl",
    "net_pnl",
    "gross_return_pct",
    "net_return_pct",
    "transaction_cost",
    "turnover",
    "cumulative_transaction_cost",
    "cost_bps",
]


def _parse_asset_list(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


def _to_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert normalized preprocessing output into strategy input format."""
    normalized = frame.copy()
    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True)
    normalized = normalized.sort_values("timestamp")
    normalized = normalized.set_index("timestamp")
    normalized.index = normalized.index.tz_convert("US/Eastern")
    renamed = normalized.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    return renamed[["Open", "High", "Low", "Close", "Volume"]]


def _build_daily_data(minute_data: pd.DataFrame) -> pd.DataFrame:
    """Derive daily OHLCV from the local intraday frame."""
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


def _result_summary_row(
    result: BacktestResult,
    *,
    asset: str,
    asset_class: str,
    strategy: str,
    split: str,
) -> dict[str, object]:
    summary = result.summary()
    return {
        "asset": asset,
        "asset_class": asset_class,
        "strategy": strategy,
        "split": split,
        "final_gross_equity": round(summary["final_gross_equity"], 2),
        "final_equity": round(summary["final_equity"], 2),
        "gross_total_return": round(summary["gross_total_return_pct"], 6),
        "net_total_return": round(summary["net_total_return_pct"], 6),
        "total_return_pct": round(summary["net_total_return_pct"], 6),
        "gross_sharpe": round(summary["gross_sharpe_ratio"], 6),
        "net_sharpe": round(summary["net_sharpe_ratio"], 6),
        "sharpe_ratio": round(summary["net_sharpe_ratio"], 6),
        "max_drawdown_pct": round(summary["max_drawdown_pct"], 6),
        "num_trades": int(summary["num_trades"]),
        "win_rate": round(summary["win_rate"], 6),
        "avg_win_pct": round(summary["avg_win_pct"], 6),
        "avg_loss_pct": round(summary["avg_loss_pct"], 6),
        "cost_bps": round(summary["cost_bps"], 6),
        "total_transaction_cost": round(summary["total_transaction_cost"], 6),
        "total_turnover": round(summary["total_turnover"], 6),
        "signal_count": len(result.signals),
    }


def _returns_rows(
    result: BacktestResult,
    *,
    asset: str,
    asset_class: str,
    strategy: str,
    split: str,
) -> list[dict[str, object]]:
    if result.equity_detail.empty:
        return []
    rows: list[dict[str, object]] = []
    for row in result.equity_detail.itertuples(index=False):
        rows.append(
            {
                "asset": asset,
                "asset_class": asset_class,
                "strategy": strategy,
                "split": split,
                "timestamp": row.timestamp,
                "gross_equity": round(float(row.gross_equity), 6),
                "net_equity": round(float(row.net_equity), 6),
                "gross_return_pct": round(float(row.gross_return_pct), 6),
                "net_return_pct": round(float(row.net_return_pct), 6),
                "turnover": round(float(row.turnover), 6),
                "transaction_cost": round(float(row.transaction_cost), 6),
                "cumulative_transaction_cost": round(float(row.cumulative_transaction_cost), 6),
            }
        )
    return rows


def _trade_rows(
    result: BacktestResult,
    *,
    asset: str,
    asset_class: str,
    strategy: str,
    split: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx, trade in enumerate(result.trades, start=1):
        rows.append(
            {
                "asset": asset,
                "asset_class": asset_class,
                "strategy": strategy,
                "split": split,
                "trade_id": idx,
                "entry_time": trade.entry_time.isoformat(),
                "exit_time": trade.exit_time.isoformat(),
                "direction": trade.direction,
                "entry_price": round(float(trade.entry_price), 6),
                "exit_price": round(float(trade.exit_price), 6),
                "leverage": round(float(trade.leverage), 6),
                "gross_pnl": round(float(trade.gross_pnl), 6),
                "net_pnl": round(float(trade.net_pnl), 6),
                "gross_return_pct": round(float(trade.gross_return_pct), 6),
                "net_return_pct": round(float(trade.net_return_pct), 6),
                "transaction_cost": round(float(trade.transaction_cost), 6),
                "turnover": round(float(trade.turnover), 6),
                "cumulative_transaction_cost": round(float(trade.cumulative_transaction_cost), 6),
                "cost_bps": round(float(result.cost_bps), 6),
            }
        )
    return rows


def _select_assets(
    *,
    asset_filter: set[str] | None = None,
    max_assets_per_class: int | None = None,
) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    counts: dict[str, int] = {}
    for asset in discover_data_files():
        if asset.frequency != "15min":
            continue
        if asset_filter and asset.asset not in asset_filter:
            continue
        counts.setdefault(asset.asset_class, 0)
        if max_assets_per_class is not None and counts[asset.asset_class] >= max_assets_per_class:
            continue
        selected.append((asset.asset, asset.asset_class))
        counts[asset.asset_class] += 1
    return selected


def run_fixed_15m_experiments(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    assets: set[str] | None = None,
    max_assets_per_class: int | None = None,
    materialize: bool = True,
    cost_config: TransactionCostConfig = DEFAULT_COST_CONFIG,
) -> dict[str, Path]:
    """Run the fixed-parameter 15-minute cross-asset baseline suite."""
    if materialize:
        materialize_processed_data()

    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    engine = BacktestEngine(initial_capital=100_000.0, cost_config=cost_config)
    summary_rows: list[dict[str, object]] = []
    split_summary_rows: list[dict[str, object]] = []
    returns_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []

    for asset, asset_class in _select_assets(
        asset_filter=assets,
        max_assets_per_class=max_assets_per_class,
    ):
        split_frames = load_all_splits(asset, asset_class, "15min")
        full_frame = pd.concat(split_frames.values(), ignore_index=True).sort_values("timestamp")
        full_minute_data = _to_market_frame(full_frame)
        full_daily_data = _build_daily_data(full_minute_data)

        for spec in STRATEGY_SPECS:
            full_result = engine.run(
                spec.factory(**spec.params),
                full_daily_data,
                full_minute_data,
                asset_class=asset_class,
                frequency="15min",
            )
            summary_rows.append(
                _result_summary_row(
                    full_result,
                    asset=asset,
                    asset_class=asset_class,
                    strategy=spec.label,
                    split="full",
                )
            )
            returns_rows.extend(
                _returns_rows(
                    full_result,
                    asset=asset,
                    asset_class=asset_class,
                    strategy=spec.label,
                    split="full",
                )
            )
            trade_rows.extend(
                _trade_rows(
                    full_result,
                    asset=asset,
                    asset_class=asset_class,
                    strategy=spec.label,
                    split="full",
                )
            )

            for split_name, split_frame in [
                ("train", split_frames["train"]),
                ("validation", split_frames["val"]),
                ("test", split_frames["test"]),
            ]:
                minute_data = _to_market_frame(split_frame)
                daily_data = _build_daily_data(minute_data)
                result = engine.run(
                    spec.factory(**spec.params),
                    daily_data,
                    minute_data,
                    asset_class=asset_class,
                    frequency="15min",
                )
                split_summary_rows.append(
                    _result_summary_row(
                        result,
                        asset=asset,
                        asset_class=asset_class,
                        strategy=spec.label,
                        split=split_name,
                    )
                )
                returns_rows.extend(
                    _returns_rows(
                        result,
                        asset=asset,
                        asset_class=asset_class,
                        strategy=spec.label,
                        split=split_name,
                    )
                )
                trade_rows.extend(
                    _trade_rows(
                        result,
                        asset=asset,
                        asset_class=asset_class,
                        strategy=spec.label,
                        split=split_name,
                    )
                )

    summary_df = pd.DataFrame(summary_rows).sort_values(["asset_class", "asset", "strategy"])
    split_summary_df = pd.DataFrame(split_summary_rows).sort_values(
        ["split", "asset_class", "asset", "strategy"]
    )
    returns_df = pd.DataFrame(returns_rows, columns=RETURN_COLUMNS)
    if not returns_df.empty:
        returns_df = returns_df.sort_values(["split", "asset_class", "asset", "strategy", "timestamp"])
    trade_df = pd.DataFrame(trade_rows, columns=TRADE_COLUMNS)
    if not trade_df.empty:
        trade_df = trade_df.sort_values(
            ["split", "asset_class", "asset", "strategy", "entry_time", "trade_id"]
        )

    paths = {
        "summary": tables_dir / TABLE_NAMES["summary"],
        "returns": tables_dir / TABLE_NAMES["returns"],
        "trades": tables_dir / TABLE_NAMES["trades"],
        "split_summary": tables_dir / TABLE_NAMES["split_summary"],
    }
    summary_df.to_csv(paths["summary"], index=False)
    split_summary_df.to_csv(paths["split_summary"], index=False)
    returns_df.to_csv(paths["returns"], index=False)
    trade_df.to_csv(paths["trades"], index=False)
    return paths


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for fixed-parameter 15-minute experiments."""
    parser = argparse.ArgumentParser(
        description="Run deterministic fixed-parameter 15-minute cross-asset experiments.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where fixed 15m output tables will be written.",
    )
    parser.add_argument(
        "--assets",
        default="",
        help="Optional comma-separated asset allowlist, e.g. AAPL,GLD,BTCUSDT.",
    )
    parser.add_argument(
        "--max-assets-per-class",
        type=int,
        default=None,
        help="Optional cap on discovered assets per asset class for smoke testing.",
    )
    parser.add_argument(
        "--skip-materialize",
        action="store_true",
        help="Skip preprocessing materialization if the processed contract already exists.",
    )
    add_cost_args(parser)
    args = parser.parse_args(argv)

    paths = run_fixed_15m_experiments(
        output_dir=Path(args.output_dir),
        assets=_parse_asset_list(args.assets),
        max_assets_per_class=args.max_assets_per_class,
        materialize=not args.skip_materialize,
        cost_config=cost_config_from_args(args),
    )
    for name, path in sorted(paths.items()):
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
