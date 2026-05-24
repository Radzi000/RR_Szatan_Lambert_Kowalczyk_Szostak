# Data README

This repository is graded on reproducibility. The final workflow therefore uses
committed repository data and does not require manual downloads.

## Files Used By The Reproduction Pipeline

- `data/1day/spy_daily.csv`
  Source: Yahoo Finance SPY daily OHLCV export.
  Date range: 2017-01-03 to 2026-05-01.
  Use in pipeline: daily volatility history and leverage scaling inputs.

- `data/5min/spy_5m.csv`
  Source: Yahoo Finance SPY 5-minute OHLCV export.
  Date range: 2026-02-06 14:30:00+00:00 to 2026-05-04 14:15:00+00:00.
  Use in pipeline: deterministic intraday backtests for Strategy0 through Strategy4.

## Additional Bundled File

- `data/spy_1m_2017_2021.csv.gz`
  Bundled archival file kept for reference only.
  It is not required by `python -m intraday_momentum.reproduce` and is not used
  by the grading workflow.

## Reproducibility Notes

- No manual download is required for grading.
- No Google Drive, Kaggle, or external storage is needed.
- `python -m intraday_momentum.reproduce` and `docker compose up --build reproduce`
  use committed data only.
- Live `yfinance` downloads are disabled in reproduce mode.

## Why Committing The Data Is Acceptable Here

The committed files are small enough for a course repository, they make the
grading workflow deterministic, and they remove failure points caused by API
limits, internet outages, and provider-side revisions.
