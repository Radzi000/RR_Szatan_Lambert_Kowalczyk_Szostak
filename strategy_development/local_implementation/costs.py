"""Centralized transaction cost assumptions and CLI helpers."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass


def _normalize_asset_class(asset_class: str | None) -> str:
    if not asset_class:
        return "default"
    normalized = asset_class.strip().lower()
    mapping = {
        "equity": "equities",
        "equities": "equities",
        "equity etf": "equities",
        "equity etfs": "equities",
        "commodity": "commodities",
        "commodities": "commodities",
        "commodity etf": "commodities",
        "commodity etfs": "commodities",
        "crypto": "crypto",
        "cryptocurrency": "crypto",
        "default": "default",
    }
    return mapping.get(normalized, "default")


@dataclass(frozen=True)
class TransactionCostConfig:
    """Per-side cost assumptions in basis points.

    Costs are charged on notional turnover when a position changes:

    - `0 -> 1` charges one side
    - `1 -> -1` charges two sides
    - partial reductions/expansions charge the proportional turnover delta
    """

    equity_cost_bps: float = 1.0
    commodity_cost_bps: float = 1.5
    crypto_cost_bps: float = 4.0
    default_cost_bps: float = 2.0

    def cost_bps_for(self, asset_class: str | None) -> float:
        normalized = _normalize_asset_class(asset_class)
        if normalized == "equities":
            return float(self.equity_cost_bps)
        if normalized == "commodities":
            return float(self.commodity_cost_bps)
        if normalized == "crypto":
            return float(self.crypto_cost_bps)
        return float(self.default_cost_bps)

    def cost_rate_for(self, asset_class: str | None) -> float:
        return self.cost_bps_for(asset_class) / 10_000.0

    def as_dict(self) -> dict[str, float]:
        return {key: float(value) for key, value in asdict(self).items()}


DEFAULT_COST_CONFIG = TransactionCostConfig()


def add_cost_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--equity-cost-bps",
        type=float,
        default=DEFAULT_COST_CONFIG.equity_cost_bps,
        help="Per-side transaction cost in bps for equities and equity ETFs.",
    )
    parser.add_argument(
        "--commodity-cost-bps",
        type=float,
        default=DEFAULT_COST_CONFIG.commodity_cost_bps,
        help="Per-side transaction cost in bps for commodity ETFs.",
    )
    parser.add_argument(
        "--crypto-cost-bps",
        type=float,
        default=DEFAULT_COST_CONFIG.crypto_cost_bps,
        help="Per-side transaction cost in bps for crypto assets.",
    )
    parser.add_argument(
        "--default-cost-bps",
        type=float,
        default=DEFAULT_COST_CONFIG.default_cost_bps,
        help="Fallback per-side transaction cost in bps for unknown asset classes.",
    )


def cost_config_from_args(args: argparse.Namespace) -> TransactionCostConfig:
    return TransactionCostConfig(
        equity_cost_bps=float(args.equity_cost_bps),
        commodity_cost_bps=float(args.commodity_cost_bps),
        crypto_cost_bps=float(args.crypto_cost_bps),
        default_cost_bps=float(args.default_cost_bps),
    )
