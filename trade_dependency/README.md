# Trade Dependency

This directory is reserved for deterministic post-trade analysis of the local
strategy outputs.

Planned topics:

- market regimes,
- volatility regimes,
- seasonality,
- time-of-day effects,
- day-of-week effects,
- dependency between consecutive trades.

## Current Status

The main Docker reproduction baseline does not depend on this directory yet.
For now it intentionally stays minimal so the repository remains clean.

## Reproducibility Rules

- no live downloads,
- no QuantConnect dependency,
- no manual notebook execution,
- all analysis should consume local artifacts generated from committed data.
