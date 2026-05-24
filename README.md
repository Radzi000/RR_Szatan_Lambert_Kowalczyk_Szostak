# Intraday Momentum Reproduction And Extension

This repository is a course project for **Reproducible Research 2026** at the
University of Warsaw (Jan Kozubowski). It reproduces and extends the intraday
momentum strategies from the upstream project
[`blackswan-quants/intraday-momentum`](https://github.com/blackswan-quants/intraday-momentum)
with a deterministic local backtesting workflow.

## Research Question

Do simple intraday momentum rules on SPY remain competitive when extended with:

- asymmetric entry and exit timing,
- EMA trend filtering,
- exit confirmation logic,
- and a combined EMA plus confirmation variant?

## Team Members

- Eryk Szatan
- Kacper Lambert
- Natalia Kowalczyk
- Radoslaw Szostak

## Upstream Project Reproduced

- Original reference: `blackswan-quants/intraday-momentum`
- This repository ports the strategy logic into an offline local Python workflow
  and compares five strategy variants on committed SPY data.

## One-Command Reproduction

```bash
git clone <repo-url>
cd RR_Szatan_Lambert_Kowalczyk_Szostak
docker compose up --build reproduce
```

This is the primary grading workflow. It:

- builds the Docker image,
- runs `python -m intraday_momentum.reproduce`,
- uses committed data only,
- generates deterministic outputs under `outputs/`,
- requires no notebooks and no local Python installation.

## Expected Outputs

After a successful run, the repository writes:

- `outputs/tables/strategy_summary.csv`
- `outputs/tables/strategy_summary.md`
- `outputs/tables/reproducibility_manifest.json`
- `outputs/figures/equity_curves.png`
- `outputs/figures/drawdowns.png`
- `outputs/report/final_report.md`

## Strategy Variants Included

- `Strategy0 / Baseline`
- `Strategy1 / Asymmetric Intervals`
- `Strategy2 / EMA Filter`
- `Strategy3 / Exit Confirmation`
- `Strategy4 / EMA + Confirmation`

## Repository Structure

```text
intraday_momentum/       Python package with data loading, strategies, backtest engine, plots, and reproduce entry point
data/                    Committed bundled data used by the grading workflow
outputs/                 Stable generated artifacts
tests/                   Offline smoke tests for reproducibility
docs/                    Sphinx documentation
notebooks/               Exploratory notebooks, not required for grading
strategy_development/    Reference strategy code snapshots
Dockerfile               Docker image definition
docker-compose.yml       Reproduction and test services
Makefile                 Local and Docker convenience targets
AI_USAGE.md              AI disclosure statement
```

## Data

The final reproducible pipeline uses committed repository data only.

- `data/1day/spy_daily.csv`
  Source: Yahoo Finance SPY daily OHLCV export.
  Date range: 2017-01-03 to 2026-05-01.

- `data/5min/spy_5m.csv`
  Source: Yahoo Finance SPY 5-minute OHLCV export.
  Date range: 2026-02-06 14:30:00+00:00 to 2026-05-04 14:15:00+00:00.

- No manual download is required.
- No internet is needed in reproduce mode.
- The pipeline does not depend on Google Drive, Kaggle, or live `yfinance`.

Additional details are documented in [data/README.md](/C:/Users/Rados/RR/data/README.md).

## Local Development

```bash
make dev
make test
make reproduce
```

Main targets:

- `make reproduce` runs `python -m intraday_momentum.reproduce`
- `make test` runs the offline pytest suite
- `make docker-reproduce` runs `docker compose up --build reproduce`
- `make docker-test` runs pytest inside Docker

## Docker

Primary command:

```bash
docker compose up --build reproduce
```

Optional:

```bash
docker compose run --rm test
docker run --rm -v ${PWD}/outputs:/app/outputs intraday-momentum-repro
```

If a Docker Hub image is published later, it can be documented here as a stable
pull target. At the moment, the repository build is the canonical workflow.

## Reproducibility Checklist

- committed input data in the repository
- deterministic CLI pipeline in `python -m intraday_momentum.reproduce`
- Docker environment for grading
- fixed strategy parameters
- stable output filenames under `outputs/`
- offline smoke tests

## AI Usage Disclosure

AI usage is disclosed in [AI_USAGE.md](/C:/Users/Rados/RR/AI_USAGE.md).

## Citations And Sources

- `blackswan-quants/intraday-momentum`, upstream strategy reference:
  https://github.com/blackswan-quants/intraday-momentum
- Yahoo Finance SPY OHLCV data, used for the committed daily and 5-minute files.

## Known Limitations

- The final grading workflow is based on the committed 5-minute SPY file rather
  than a longer 2-minute research dataset.
- Intraday history is limited to the committed file range, so the project favors
  deterministic reproducibility over broader data coverage.
- Exploratory notebooks remain in the repository for transparency, but they are
  not required by the grading workflow.

## Acknowledgment Guidance

If this repository is cited or reused, please acknowledge both the upstream
`blackswan-quants/intraday-momentum` project and this course reproduction.
