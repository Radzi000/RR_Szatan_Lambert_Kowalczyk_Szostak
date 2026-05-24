# Intraday Momentum Reproduction And Extension

This repository is a course project for **Reproducible Research 2026** at the
University of Warsaw (Jan Kozubowski). It reproduces and extends five
QuantConnect-style intraday momentum strategies from the upstream project
[`blackswan-quants/intraday-momentum`](https://github.com/blackswan-quants/intraday-momentum)
with a fully local, deterministic, Dockerized workflow.

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

## Project Story

The repository is organized around one research pipeline:

```text
data
-> preprocessing
-> strategy_development
-> trade_dependency
-> final_portfolio
-> outputs
```

Within that pipeline:

- the original downloaded QuantConnect-style strategies are preserved as
  reference-only artifacts under `strategy_development/taken_strategies/`,
- the authoritative local implementation lives under
  `strategy_development/local_implementation/`,
- the local Docker pipeline is the only execution path required for grading.

## Upstream Project Reproduced

- Original reference: `blackswan-quants/intraday-momentum`
- Original downloaded QuantConnect-style strategy files are preserved under
  `strategy_development/taken_strategies/`.
- The authoritative local implementation lives in
  `strategy_development/local_implementation/`.

## QuantConnect Status

QuantConnect is treated as a **source/reference format only**.

This repository does **not** depend on:

- QuantConnect cloud,
- QuantConnect APIs,
- Lean CLI,
- a QuantConnect account,
- public QuantConnect backtests at runtime.

The local Docker pipeline is authoritative for grading and reproducibility.

## One-Command Reproduction

```bash
git clone <repo-url>
cd RR_Szatan_Lambert_Kowalczyk_Szostak
docker compose up --build reproduce
```

This is the primary grading workflow. It:

- builds the Docker image,
- runs `python -m strategy_development.local_implementation.reproduce`,
- uses committed data only,
- generates deterministic outputs under `outputs/`,
- does not require QuantConnect,
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
data/                               Committed baseline and extension datasets
preprocessing/                      Deterministic data manifest, validation, and split helpers
strategy_development/               Original reference strategies plus local implementation
trade_dependency/                   Future research area for dependency analysis
final_portfolio/                    Future research area for portfolio construction
outputs/                            Generated reproducible artifacts
tests/                              Offline smoke tests
docs/                               Useful project documentation
Dockerfile                          Docker image definition
docker-compose.yml                  Canonical reproducible services
Makefile                            Convenience commands
AI_USAGE.md                         AI disclosure statement
```

## Data

The final reproducible pipeline uses committed repository data only.

- `data/1day/spy_daily.csv`
  Source: Yahoo Finance SPY daily OHLCV export.
  Date range: 2017-01-03 to 2026-05-01.

- `data/5min/spy_5m.csv`
  Source: Yahoo Finance SPY 5-minute OHLCV export.
  Date range: 2026-02-06 14:30:00+00:00 to 2026-05-04 14:15:00+00:00.

- `data/15min/equities/`
  Committed 15-minute equity data used for the broader research extension.

- `data/15min/commodities/`
  Committed 15-minute commodity ETF proxy data used for the broader research
  extension.

- `data/15min/crypto/`
  Committed 15-minute crypto data used for the broader research extension.

- `5m SPY` is the faithful local reproduction baseline.
- `15m` is the intended main research extension frequency.
- `30m` data is not required for this repository.

- No manual download is required.
- No internet is needed in reproduce mode.
- The pipeline does not depend on Google Drive, Kaggle, or live `yfinance`.

Additional details are documented in [data/README.md](/C:/Users/Rados/RR/data/README.md).

## Local Development

```bash
make dev
make test
make data-manifest
make splits
make preprocess
make reproduce
```

Main targets:

- `make data-manifest` builds a deterministic raw-data manifest
- `make splits` computes deterministic global split boundaries for the 15-minute extension layer
- `make preprocess` runs both preprocessing steps
- `make reproduce` runs `python -m strategy_development.local_implementation.reproduce`
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
- deterministic preprocessing utilities in `preprocessing/`
- deterministic CLI pipeline in `python -m strategy_development.local_implementation.reproduce`
- Docker environment for grading
- fixed strategy parameters
- stable output filenames under `outputs/`
- offline smoke tests

## AI Usage Disclosure

AI usage is disclosed in [AI_USAGE.md](/C:/Users/Rados/RR/AI_USAGE.md).

## Citations And Sources

- `blackswan-quants/intraday-momentum`, upstream strategy reference:
  https://github.com/blackswan-quants/intraday-momentum
- Yahoo Finance and other committed local OHLCV exports used for the data files
  stored in `data/`.

## Known Limitations

- The final grading workflow is based on the committed 5-minute SPY file rather
  than a larger intraday baseline.
- The broader 15-minute cross-asset extension is not yet the canonical Docker
  reproduce workflow.
- Intraday history is limited to the committed files, so the project favors
  deterministic reproducibility over unrestricted data coverage.

## Acknowledgment Guidance

If this repository is cited or reused, please acknowledge both the upstream
`blackswan-quants/intraday-momentum` project and this course reproduction.
