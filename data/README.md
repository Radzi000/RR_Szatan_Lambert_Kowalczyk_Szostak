# Market Data

This directory contains bundled SPY data for reproducibility.

## Included Files

- `spy_daily.csv` — Daily OHLCV data, 2017–2026 (~2300 trading days)
- `spy_5m.csv` — 5-minute intraday bars, last 60 days (~4600 bars)

These files are downloaded from Yahoo Finance and are sufficient to run
all strategies and reproduce our results.

## Getting More Data

For longer intraday history, you can download from Kaggle:

```bash
# Install Kaggle CLI
pip install kaggle

# Download SPY 1-minute data 2008-2021 (~23 MB)
kaggle datasets download -d rockinbrock/spy-1-minute-data -p data/
unzip data/spy-1-minute-data.zip -d data/
```

## Refreshing Data

To download fresh data from Yahoo Finance:

```bash
make download-data
```
