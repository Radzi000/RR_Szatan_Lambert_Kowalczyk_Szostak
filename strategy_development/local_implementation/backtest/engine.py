"""Backtesting engine for local intraday momentum strategies."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..costs import DEFAULT_COST_CONFIG, TransactionCostConfig
from ..strategies.base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


def _annualization_factor(index: pd.Index) -> float:
    if len(index) < 2:
        return 252.0
    timestamps = pd.to_datetime(index)
    delta = timestamps.to_series().diff().dropna().median()
    if pd.isna(delta) or delta <= pd.Timedelta(0):
        return 252.0
    minutes = delta.total_seconds() / 60.0
    if minutes >= 24 * 60:
        return 252.0
    bars_per_day = max((6.5 * 60) / max(minutes, 1e-9), 1.0)
    return 252.0 * bars_per_day


def _max_drawdown_pct(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    peak = equity_curve.cummax()
    drawdown = (equity_curve / peak - 1.0) * 100.0
    return float(drawdown.min())


@dataclass
class Trade:
    """Record of a single closed position segment."""

    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: int
    entry_price: float
    exit_price: float
    leverage: float
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    transaction_cost: float = 0.0
    turnover: float = 0.0
    cumulative_transaction_cost: float = 0.0
    gross_return_pct: float = 0.0
    net_return_pct: float = 0.0

    @property
    def pnl(self) -> float:
        return self.net_pnl

    @property
    def return_pct(self) -> float:
        return self.net_return_pct


@dataclass
class BacktestResult:
    """Container for gross and net backtest outputs."""

    gross_equity_curve: pd.Series
    net_equity_curve: pd.Series
    equity_detail: pd.DataFrame
    trades: list[Trade] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    initial_capital: float = 100_000.0
    final_equity: float = 0.0
    final_gross_equity: float = 0.0
    total_transaction_cost: float = 0.0
    total_turnover: float = 0.0
    cost_bps: float = 0.0
    asset_class: str = "default"
    frequency: str = ""

    @property
    def equity_curve(self) -> pd.Series:
        return self.net_equity_curve

    @property
    def total_return(self) -> float:
        return (self.final_equity / self.initial_capital - 1.0) * 100.0

    @property
    def gross_total_return(self) -> float:
        return (self.final_gross_equity / self.initial_capital - 1.0) * 100.0

    @property
    def num_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for trade in self.trades if trade.net_pnl > 0)
        return wins / len(self.trades)

    def summary(self) -> dict[str, float]:
        net_returns = self.net_equity_curve.pct_change().dropna()
        gross_returns = self.gross_equity_curve.pct_change().dropna()
        annualization = _annualization_factor(self.net_equity_curve.index)

        net_sharpe = 0.0
        if len(net_returns) > 1 and net_returns.std() > 0:
            net_sharpe = float((net_returns.mean() / net_returns.std()) * np.sqrt(annualization))

        gross_sharpe = 0.0
        if len(gross_returns) > 1 and gross_returns.std() > 0:
            gross_sharpe = float((gross_returns.mean() / gross_returns.std()) * np.sqrt(annualization))

        avg_win = 0.0
        avg_loss = 0.0
        wins = [trade.net_return_pct for trade in self.trades if trade.net_pnl > 0]
        losses = [trade.net_return_pct for trade in self.trades if trade.net_pnl <= 0]
        if wins:
            avg_win = float(np.mean(wins))
        if losses:
            avg_loss = float(np.mean(losses))

        return {
            "initial_capital": float(self.initial_capital),
            "final_equity": float(self.final_equity),
            "final_gross_equity": float(self.final_gross_equity),
            "total_return_pct": float(self.total_return),
            "gross_total_return_pct": float(self.gross_total_return),
            "net_total_return_pct": float(self.total_return),
            "sharpe_ratio": net_sharpe,
            "net_sharpe_ratio": net_sharpe,
            "gross_sharpe_ratio": gross_sharpe,
            "max_drawdown_pct": _max_drawdown_pct(self.net_equity_curve.astype(float)),
            "gross_max_drawdown_pct": _max_drawdown_pct(self.gross_equity_curve.astype(float)),
            "num_trades": int(self.num_trades),
            "win_rate": float(self.win_rate),
            "avg_win_pct": avg_win,
            "avg_loss_pct": avg_loss,
            "total_transaction_cost": float(self.total_transaction_cost),
            "total_turnover": float(self.total_turnover),
            "cost_bps": float(self.cost_bps),
        }


class BacktestEngine:
    """Execute a strategy and deduct turnover-based transaction costs."""

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_per_share: float = 0.0,
        cost_config: TransactionCostConfig | None = None,
    ) -> None:
        self.initial_capital = initial_capital
        self.commission_per_share = commission_per_share
        self.cost_config = cost_config or DEFAULT_COST_CONFIG

    @staticmethod
    def _position_delta(current_exposure: float, target_exposure: float) -> tuple[float, float]:
        current_abs = abs(current_exposure)
        target_abs = abs(target_exposure)
        current_sign = np.sign(current_exposure)
        target_sign = np.sign(target_exposure)

        if current_abs == 0.0:
            return 0.0, target_abs
        if target_abs == 0.0:
            return current_abs, 0.0
        if current_sign != target_sign:
            return current_abs, target_abs
        if target_abs >= current_abs:
            return 0.0, target_abs - current_abs
        return current_abs - target_abs, 0.0

    def run(
        self,
        strategy: BaseStrategy,
        daily_data: pd.DataFrame,
        minute_data: pd.DataFrame,
        *,
        asset_class: str = "default",
        frequency: str = "",
    ) -> BacktestResult:
        signals = strategy.generate_signals(daily_data, minute_data)
        logger.info("Generated %d signals", len(signals))

        cost_bps = self.cost_config.cost_bps_for(asset_class)
        cost_rate = self.cost_config.cost_rate_for(asset_class)
        gross_equity = float(self.initial_capital)
        net_equity = float(self.initial_capital)
        total_transaction_cost = 0.0
        total_turnover = 0.0
        trades: list[Trade] = []
        equity_rows: list[dict[str, float | str]] = []

        current_exposure = 0.0
        entry_price = 0.0
        entry_time: pd.Timestamp | None = None
        entry_notional = 0.0
        entry_equity_base = 0.0
        open_trade_entry_cost = 0.0
        open_trade_entry_turnover = 0.0

        def _append_equity_row(
            timestamp: pd.Timestamp,
            price: float,
            target_exposure: float,
            event_turnover: float,
            event_cost: float,
            gross_before_event: float,
            net_before_event: float,
        ) -> None:
            gross_return_pct = 0.0
            net_return_pct = 0.0
            if gross_before_event > 0:
                gross_return_pct = ((gross_equity / gross_before_event) - 1.0) * 100.0
            if net_before_event > 0:
                net_return_pct = ((net_equity / net_before_event) - 1.0) * 100.0
            equity_rows.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "price": float(price),
                    "target_exposure": float(target_exposure),
                    "gross_equity": float(gross_equity),
                    "net_equity": float(net_equity),
                    "gross_return_pct": float(gross_return_pct),
                    "net_return_pct": float(net_return_pct),
                    "turnover": float(event_turnover),
                    "transaction_cost": float(event_cost),
                    "cumulative_transaction_cost": float(total_transaction_cost),
                }
            )

        for signal in signals:
            price = minute_data.loc[signal.timestamp, "Close"]
            if isinstance(price, pd.Series):
                price = price.iloc[0]
            price = float(price)
            target_exposure = float(signal.direction) * abs(float(signal.leverage))
            gross_before_event = gross_equity
            net_before_event = net_equity
            event_turnover = 0.0
            event_cost = 0.0

            if not np.isclose(target_exposure, current_exposure):
                close_exposure, open_exposure = self._position_delta(current_exposure, target_exposure)

                if current_exposure != 0.0 and entry_time is not None and entry_price > 0.0:
                    direction = 1 if current_exposure > 0 else -1
                    gross_trade_pnl = direction * ((price - entry_price) / entry_price) * entry_notional
                    gross_equity += gross_trade_pnl
                    net_equity += gross_trade_pnl

                    close_turnover = max(net_equity, 0.0) * close_exposure
                    close_cost = close_turnover * cost_rate
                    net_equity -= close_cost
                    total_turnover += close_turnover
                    total_transaction_cost += close_cost
                    event_turnover += close_turnover
                    event_cost += close_cost

                    trade_cost = open_trade_entry_cost + close_cost
                    trade_turnover = open_trade_entry_turnover + close_turnover
                    trade_net_pnl = gross_trade_pnl - trade_cost
                    gross_return_pct = 0.0
                    net_return_pct = 0.0
                    if entry_equity_base > 0:
                        gross_return_pct = (gross_trade_pnl / entry_equity_base) * 100.0
                        net_return_pct = (trade_net_pnl / entry_equity_base) * 100.0

                    trades.append(
                        Trade(
                            entry_time=entry_time,
                            exit_time=signal.timestamp,
                            direction=direction,
                            entry_price=float(entry_price),
                            exit_price=price,
                            leverage=abs(float(current_exposure)),
                            gross_pnl=float(gross_trade_pnl),
                            net_pnl=float(trade_net_pnl),
                            transaction_cost=float(trade_cost),
                            turnover=float(trade_turnover),
                            cumulative_transaction_cost=float(total_transaction_cost),
                            gross_return_pct=float(gross_return_pct),
                            net_return_pct=float(net_return_pct),
                        )
                    )

                current_exposure = 0.0
                entry_price = 0.0
                entry_time = None
                entry_notional = 0.0
                entry_equity_base = 0.0
                open_trade_entry_cost = 0.0
                open_trade_entry_turnover = 0.0

                if target_exposure != 0.0:
                    open_turnover = max(net_equity, 0.0) * open_exposure
                    open_cost = open_turnover * cost_rate
                    net_equity -= open_cost
                    total_turnover += open_turnover
                    total_transaction_cost += open_cost
                    event_turnover += open_turnover
                    event_cost += open_cost

                    current_exposure = target_exposure
                    entry_price = price
                    entry_time = signal.timestamp
                    entry_equity_base = max(net_equity, 0.0)
                    entry_notional = entry_equity_base * abs(current_exposure)
                    open_trade_entry_cost = open_cost
                    open_trade_entry_turnover = open_turnover

            _append_equity_row(
                signal.timestamp,
                price,
                target_exposure,
                event_turnover,
                event_cost,
                gross_before_event,
                net_before_event,
            )

        if current_exposure != 0.0 and not minute_data.empty and entry_time is not None and entry_price > 0.0:
            final_timestamp = minute_data.index[-1]
            final_price = float(minute_data.iloc[-1]["Close"])
            gross_before_event = gross_equity
            net_before_event = net_equity
            close_exposure = abs(current_exposure)
            direction = 1 if current_exposure > 0 else -1
            gross_trade_pnl = direction * ((final_price - entry_price) / entry_price) * entry_notional
            gross_equity += gross_trade_pnl
            net_equity += gross_trade_pnl
            close_turnover = max(net_equity, 0.0) * close_exposure
            close_cost = close_turnover * cost_rate
            net_equity -= close_cost
            total_turnover += close_turnover
            total_transaction_cost += close_cost

            trade_cost = open_trade_entry_cost + close_cost
            trade_turnover = open_trade_entry_turnover + close_turnover
            trade_net_pnl = gross_trade_pnl - trade_cost
            gross_return_pct = 0.0
            net_return_pct = 0.0
            if entry_equity_base > 0:
                gross_return_pct = (gross_trade_pnl / entry_equity_base) * 100.0
                net_return_pct = (trade_net_pnl / entry_equity_base) * 100.0

            trades.append(
                Trade(
                    entry_time=entry_time,
                    exit_time=final_timestamp,
                    direction=direction,
                    entry_price=float(entry_price),
                    exit_price=final_price,
                    leverage=abs(float(current_exposure)),
                    gross_pnl=float(gross_trade_pnl),
                    net_pnl=float(trade_net_pnl),
                    transaction_cost=float(trade_cost),
                    turnover=float(trade_turnover),
                    cumulative_transaction_cost=float(total_transaction_cost),
                    gross_return_pct=float(gross_return_pct),
                    net_return_pct=float(net_return_pct),
                )
            )
            _append_equity_row(
                final_timestamp,
                final_price,
                0.0,
                close_turnover,
                close_cost,
                gross_before_event,
                net_before_event,
            )

        equity_detail = pd.DataFrame(equity_rows)
        if equity_detail.empty:
            gross_equity_curve = pd.Series(dtype=float, name="gross_equity")
            net_equity_curve = pd.Series(dtype=float, name="net_equity")
        else:
            timestamps = pd.to_datetime(equity_detail["timestamp"], utc=True)
            gross_equity_curve = pd.Series(equity_detail["gross_equity"].to_numpy(), index=timestamps, name="gross_equity")
            net_equity_curve = pd.Series(equity_detail["net_equity"].to_numpy(), index=timestamps, name="net_equity")

        return BacktestResult(
            gross_equity_curve=gross_equity_curve,
            net_equity_curve=net_equity_curve,
            equity_detail=equity_detail,
            trades=trades,
            signals=signals,
            initial_capital=float(self.initial_capital),
            final_equity=float(net_equity),
            final_gross_equity=float(gross_equity),
            total_transaction_cost=float(total_transaction_cost),
            total_turnover=float(total_turnover),
            cost_bps=float(cost_bps),
            asset_class=asset_class,
            frequency=frequency,
        )
