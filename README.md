# Intraday Momentum Reproduction And Extension

This repository is a **Reproducible Research 2026** course project at the
University of Warsaw. It reproduces and extends five QuantConnect-style
intraday momentum strategies from
[`blackswan-quants/intraday-momentum`](https://github.com/blackswan-quants/intraday-momentum)
using committed offline data, committed result artifacts, and a Dockerized
Quarto report renderer.

## Quick Start For Reviewers

The reviewer workflow is Docker-only:

```bash
docker pull <dockerhub-user>/intraday-momentum-repro:latest
docker run --rm -v "$PWD/reproduction-artifacts:/artifacts" <dockerhub-user>/intraday-momentum-repro:latest
```

Windows PowerShell:

```powershell
docker pull <dockerhub-user>/intraday-momentum-repro:latest
docker run --rm -v "${PWD}\reproduction-artifacts:/artifacts" <dockerhub-user>/intraday-momentum-repro:latest
```

Expected output:

```text
reproduction-artifacts/reports/final_report.html
reproduction-artifacts/outputs/
```

No local Python, Quarto, notebooks, QuantConnect, Lean CLI, or manual data
downloads are required.

## What Docker Does

The Docker image contains the complete committed repository contents, including
`outputs/`. Those committed outputs are intentional: they are the canonical
inputs used by the final report.

The default container command only renders:

```bash
quarto render reports/final_report.qmd
```

Then it exports:

- `reports/final_report.html` to `reproduction-artifacts/reports/final_report.html`
- committed `outputs/` to `reproduction-artifacts/outputs/`

The reviewer Docker command does **not** rerun preprocessing, strategy
experiments, optimizations, or portfolio construction. It renders the Quarto
report from the existing committed artifacts.

## Repository Structure

```text
data/                         Committed raw and processed datasets
preprocessing/                Deterministic data manifest and split utilities
strategy_development/         Reference strategies and local implementation
trade_dependency/             Trade autocorrelation analysis code
final_portfolio/              Portfolio construction code
outputs/                      Committed canonical report inputs
reports/final_report.qmd      Final Quarto report source
tests/                        Offline smoke tests
Dockerfile                    Docker image definition
docker-compose.yml            Optional local developer services
scripts/docker_render_report.sh
AI_USAGE.md                   AI usage disclosure
```

## Research Question

Do simple intraday momentum rules on SPY remain competitive when extended with:

- asymmetric entry and exit timing,
- EMA trend filtering,
- exit confirmation logic,
- and a combined EMA plus confirmation variant?

The included strategy variants are:

- `Strategy0 / Baseline`
- `Strategy1 / Asymmetric Intervals`
- `Strategy2 / EMA Filter`
- `Strategy3 / Exit Confirmation`
- `Strategy4 / EMA + Confirmation`

## Data And Reproducibility Assumptions

The project uses committed offline data only. The report and Docker reviewer
workflow do not perform live downloads.

Committed data includes:

- `data/1day/spy_daily.csv`
- `data/5min/spy_5m.csv`
- `data/15min/equities/`
- `data/15min/commodities/`
- `data/15min/crypto/`
- processed handoff files under `data/processed/`

`outputs/` is committed intentionally. It contains the tables, figures, and
markdown summaries read by `reports/final_report.qmd`. Rendered Quarto outputs
such as `reports/*.html`, `reports/*.pdf`, `.quarto/`, and report cache
directories are not committed.

QuantConnect is treated as a source/reference format only. The project does not
depend on QuantConnect cloud, QuantConnect APIs, Lean CLI, a QuantConnect
account, or public QuantConnect backtests at runtime.

## Local Development

Reviewer reproduction does not require these commands. They are for maintainers
who want to inspect or regenerate artifacts locally.

```bash
pytest
python -m strategy_development.local_implementation.reproduce
python -m strategy_development.local_implementation.run_fixed_15m_experiments
python -m strategy_development.local_implementation.optimization.run_all_optimizations --smoke
python -m final_portfolio.run_report
quarto render reports/final_report.qmd
```

Equivalent Make targets:

```bash
make test
make reproduce
make fixed-15m
make optimize-smoke
make final-portfolio
make report
```

Local Docker build and report render:

```bash
docker build -t intraday-momentum-repro .
docker run --rm -v "$PWD/reproduction-artifacts:/artifacts" intraday-momentum-repro
```

Optional developer Compose services remain available, but they are not the
primary reviewer workflow:

```bash
docker compose run --rm test
docker compose up --build report
```

## Maintainer Docker Publish

Replace `<dockerhub-user>` with the publishing account:

```bash
docker build -t <dockerhub-user>/intraday-momentum-repro:latest .
docker push <dockerhub-user>/intraday-momentum-repro:latest
```

After publishing, reviewers should use the two-command Docker Hub workflow at
the top of this README.

## Team Members

- Eryk Szatan
- Kacper Lambert
- Natalia Kowalczyk
- Radoslaw Szostak

## AI Usage

AI usage is disclosed in [AI_USAGE.md](AI_USAGE.md).

## Citations And Sources

- Upstream strategy reference:
  [`blackswan-quants/intraday-momentum`](https://github.com/blackswan-quants/intraday-momentum)
- Yahoo Finance and other offline OHLCV exports are stored as committed files
  under `data/`.

## Known Limitations

- The reviewer Docker workflow renders the final report from committed
  artifacts; it does not recompute the full research pipeline.
- Intraday history is limited to the committed files, favoring deterministic
  reproducibility over unrestricted data coverage.
- Validation results are used for model and parameter selection; final
  out-of-sample claims should be read with that boundary in mind.
- Daily data is excluded from some cost-aware strategy curve plots because the
  implemented strategy logic is intraday-specific.

## Acknowledgment Guidance

If this repository is cited or reused, please acknowledge both the upstream
`blackswan-quants/intraday-momentum` project and this course reproduction.
