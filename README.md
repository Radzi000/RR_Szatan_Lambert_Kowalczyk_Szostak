# Intraday Momentum — Reproducible Research

> Quantitative Analysis of Intraday Momentum via Volatility Regimes, Trend Filtering, and Temporal Persistence

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

## Overview

This project reproduces and extends the intraday momentum trading strategies from
[blackswan-quants/intraday-momentum](https://github.com/blackswan-quants/intraday-momentum).
The original strategies were implemented for the QuantConnect cloud platform — we convert them
to run locally with `yfinance` data, add evaluation tools, and package everything for full
reproducibility.

## Team

- **Eryk Szatan**
- **Kacper Rickie Lambert**
- **Natalia Kowalczyk**
- **Radosław Szostak**

*University of Warsaw — Reproducible Research (Jan Kozubowski)*

## Strategies

| # | Name | Key Feature |
|---|------|-------------|
| 0 | Baseline | VWAP exit, 30-min entry checks |
| 1 | Asymmetric Intervals | Fast exits (5 min), slow entries (30 min) |
| 2 | EMA Filter | 100-period EMA trend confirmation |
| 3 | Exit Confirmation | Counter-based exit (4 consecutive bars) |
| 4 | EMA + Confirmation | Combined EMA filter and confirmed exits |

## Quick Start

### Local Setup

```bash
git clone https://github.com/Radzi000/RR_Szatan_Lambert_Kowalczyk_Szostak.git
cd RR_Szatan_Lambert_Kowalczyk_Szostak
make dev        # install deps + pre-commit hooks
make test       # run tests
make docs       # build Sphinx documentation
```

### Docker

```bash
make docker-build
docker compose run --rm app       # run tests
docker compose run --rm backtest  # run strategies
```

### Run a Backtest

```python
from intraday_momentum.data.provider import DataProvider
from intraday_momentum.strategies import Strategy0
from intraday_momentum.backtest.engine import BacktestEngine

provider = DataProvider("SPY")
daily = provider.get_daily_data("2023-01-01", "2023-12-31")
minute = provider.get_data("2023-11-01", "2023-12-31")

strategy = Strategy0(lookback=14, vol_target=0.02)
engine = BacktestEngine(initial_capital=100_000)
result = engine.run(strategy, daily, minute)
print(result.summary())
```

## Project Structure

```
├── intraday_momentum/       # Main Python package
│   ├── strategies/          # Strategy implementations (0-4)
│   ├── backtest/            # Backtesting engine
│   ├── data/                # Data provider (yfinance)
│   ├── evaluation/          # Performance metrics
│   └── visualization/       # Plotting utilities
├── strategy_development/    # Original QuantConnect code (reference)
├── notebooks/               # Jupyter/Marimo experimentation
├── tests/                   # pytest test suite
├── docs/                    # Sphinx documentation
├── Dockerfile               # Container definition
├── docker-compose.yml       # Service orchestration
├── Makefile                 # Automation targets
└── pyproject.toml           # Project config, deps, linting
```

## Makefile Targets

Run `make help` to see all available targets:
`install`, `dev`, `lint`, `format`, `test`, `docs`, `docker-build`, `docker-test`, `backtest`, `clean`.
