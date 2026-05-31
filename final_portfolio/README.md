# Final Portfolio

Portfolio construction layer built on top of Workstream C multi-asset equity curves.

Input: `outputs/tables/equity_curves_our_strats.csv` — 5 strategies x 7 assets
(AAPL, BTCUSDT, ETHUSDT, GLD, MSFT, NVDA, USO), parameters tuned via Workstream C
optimization (grid search / NES / CMA-ES). Train: Aug 2020 – Jun 2024.
Validation: Jul 2024 – Apr 2025.

## Methods

- **Equal-weight** (`equal_weight.py`): 1/N allocation across all 35 instruments, baseline.
- **Kelly** (`kelly.py`): Half-Kelly weights from rolling per-trade win-rate and R-ratio.
  Bar-level returns are aggregated into per-trade returns before Kelly statistics are computed.
  Grid search over lookback (trades) x rebalancing (days).
- **Markowitz** (`markowitz.py`): Maximum-Sharpe MVO using scipy SLSQP.
  Calendar-day rolling window ensures equities and crypto are evaluated over the same horizon.
  Grid search over lookback (calendar days) x rebalancing (days).
- **Trade dependency** (`trade_dependency.py`): Lag-1 autocorrelation analysis per instrument.
  Weight adjustment multiplier applied on top of Kelly and Markowitz base weights.

## Results (best parameters selected on train split)

| Method             | Train Sharpe | Val Sharpe | Val Return | Val MaxDD |
|--------------------|:------------:|:----------:|:----------:|:---------:|
| Equal-weight       | 0.273        | 0.568      | +3.7%      | −13.1%    |
| Kelly (50t, 30d)   | 0.811        | 0.443      | +5.3%      | −20.6%    |
| Markowitz (90d, 30d) | 0.698      | 1.299      | +5.0%      | −5.8%     |

## Reproducing

```bash
make final-portfolio
```

Runs grid searches, generates all figures to `outputs/figures/final_portfolio_*.png`,
and saves a markdown report to `outputs/report/final_portfolio_report.md`.

Requires `outputs/tables/equity_curves_our_strats.csv` produced by `make optimize`.
