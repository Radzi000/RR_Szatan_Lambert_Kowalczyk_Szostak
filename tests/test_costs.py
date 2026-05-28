from __future__ import annotations

import pandas as pd

from strategy_development.local_implementation.backtest.engine import BacktestEngine
from strategy_development.local_implementation.costs import TransactionCostConfig
from strategy_development.local_implementation.strategies.base import BaseStrategy, Signal


class TwoSignalStrategy(BaseStrategy):
    def generate_signals(self, daily_data: pd.DataFrame, minute_data: pd.DataFrame) -> list[Signal]:
        timestamps = list(minute_data.index)
        return [
            Signal(timestamp=timestamps[0], direction=1, leverage=1.0, reason="enter"),
            Signal(timestamp=timestamps[-1], direction=0, leverage=0.0, reason="exit"),
        ]


def _sample_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    minute_index = pd.to_datetime(
        [
            "2026-01-05 14:30:00+00:00",
            "2026-01-05 14:45:00+00:00",
        ]
    )
    minute_data = pd.DataFrame(
        {
            "Open": [100.0, 102.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 101.0],
            "Close": [100.0, 102.0],
            "Volume": [1_000.0, 1_200.0],
        },
        index=minute_index,
    )
    daily_data = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [103.0],
            "Low": [99.0],
            "Close": [102.0],
            "Volume": [2_200.0],
        },
        index=pd.to_datetime(["2026-01-05"]),
    )
    daily_data.index.name = "Date"
    return daily_data, minute_data


def test_transaction_cost_config_maps_asset_classes() -> None:
    config = TransactionCostConfig()
    assert config.cost_bps_for("equities") == 1.0
    assert config.cost_bps_for("commodities") == 1.5
    assert config.cost_bps_for("crypto") == 4.0
    assert config.cost_bps_for("unknown") == 2.0


def test_transaction_costs_reduce_net_results_when_trades_occur() -> None:
    daily_data, minute_data = _sample_frames()
    gross_engine = BacktestEngine(
        initial_capital=100_000.0,
        cost_config=TransactionCostConfig(
            equity_cost_bps=0.0,
            commodity_cost_bps=0.0,
            crypto_cost_bps=0.0,
            default_cost_bps=0.0,
        ),
    )
    net_engine = BacktestEngine(initial_capital=100_000.0, cost_config=TransactionCostConfig())

    gross_result = gross_engine.run(
        TwoSignalStrategy(),
        daily_data,
        minute_data,
        asset_class="equities",
        frequency="15min",
    )
    net_result = net_engine.run(
        TwoSignalStrategy(),
        daily_data,
        minute_data,
        asset_class="equities",
        frequency="15min",
    )

    assert gross_result.total_transaction_cost == 0.0
    assert net_result.total_transaction_cost > 0.0
    assert gross_result.final_equity > net_result.final_equity
    assert net_result.trades[0].gross_pnl > net_result.trades[0].net_pnl
