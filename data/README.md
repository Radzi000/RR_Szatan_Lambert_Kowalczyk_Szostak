# Data README

This repository is graded on reproducibility. The final workflow therefore uses
committed repository data and does not require manual downloads.

## Current Frequency Layers

- `data/1day/`
  Baseline daily files for realized-volatility inputs and other slower features.

- `data/5min/`
  Faithful local reproduction baseline for SPY intraday strategy execution.

- `data/15min/equities/`
  Main committed cross-asset extension data for equities.

- `data/15min/commodities/`
  Main committed cross-asset extension data for commodity ETF proxies.

- `data/15min/crypto/`
  Main committed cross-asset extension data for crypto.

The repository does **not** require 30-minute data.

## Files Used By The Current Reproduction Pipeline

- `data/1day/spy_daily.csv`
  Source: Yahoo Finance SPY daily OHLCV export.
  Date range: 2017-01-03 to 2026-05-01.
  Use in pipeline: daily volatility history and leverage scaling inputs.

- `data/5min/spy_5m.csv`
  Source: Yahoo Finance SPY 5-minute OHLCV export.
  Date range: 2026-02-06 14:30:00+00:00 to 2026-05-04 14:15:00+00:00.
  Use in pipeline: deterministic intraday backtests for Strategy0 through Strategy4.

## Files Intended For The 15-Minute Research Extension

- `data/15min/equities/*.csv`
  Committed 15-minute equity datasets.
- `data/15min/commodities/*.csv`
  Committed 15-minute commodity ETF proxy datasets.
- `data/15min/crypto/*.csv`
  Committed 15-minute crypto datasets.

These 15-minute files are intended for the broader research extension layer:

- cross-asset experiments,
- deterministic global train/validation/test splits,
- adapted 15-minute strategy execution,
- trade-dependency analysis,
- final out-of-sample portfolio construction.

Interpretation rule:

- `5m SPY` is the faithful local reproduction baseline.
- `15m` is the main adapted extension frequency.
- Original `30m` entry logic is adapted on `15m` as every 2 bars.
- Faster original exit checks are adapted on `15m` as every 1 bar.
- Original confirmation logic can be documented as a `2 x 15m` analogue or as
  a later parameterized adaptation.

## Additional Bundled File

- `data/spy_1m_2017_2021.csv.gz`
  Bundled archival file kept for reference only.
  It is not required by `python -m strategy_development.local_implementation.reproduce` and is not used
  by the grading workflow.

## Reproducibility Notes

- No manual download is required for grading.
- No Google Drive, Kaggle, or external storage is needed.
- `python -m strategy_development.local_implementation.reproduce` and `docker compose up --build reproduce`
  use committed data only.
- Live `yfinance` downloads are disabled in reproduce mode.

## Schema Expectations

The preprocessing layer normalizes datasets to the shared schema:

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`

Additional deterministic metadata should be attached during preprocessing:

- `asset`
- `asset_class`
- `frequency`
- `source_file`

Current raw files are allowed to differ in column names and timestamp formatting
as long as the preprocessing layer can normalize them deterministically.

## Why Committing The Data Is Acceptable Here

The committed files are small enough for a course repository, they make the
grading workflow deterministic, and they remove failure points caused by API
limits, internet outages, and provider-side revisions.
