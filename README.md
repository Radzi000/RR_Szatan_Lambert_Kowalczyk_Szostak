# Intraday Momentum Reproduction And Extension

This University of Warsaw reproducible-research project locally reproduces and
extends five QuantConnect-style intraday momentum strategies using committed
offline data and deterministic outputs. QuantConnect and Lean are references
only; neither is required at runtime.

## Workflow 1: Pull And Run The Prebuilt Image

```bash
docker pull radek1715/intraday-momentum-repro:latest
docker run --rm radek1715/intraday-momentum-repro:latest
```

The image default runs exactly:

```bash
python -m strategy_development.local_implementation.reproduce
```

It does not render Quarto, start Jupyter, run optimization, or download data.
Quarto remains installed in the image for the separate report workflow below.

## Workflow 2: Clone And Reproduce Through Compose

```bash
git clone https://github.com/Radzi000/RR_Szatan_Lambert_Kowalczyk_Szostak RR
cd RR
docker compose up --build reproduce
```

The bind-mounted `outputs/` directory receives the lightweight reproduction
artifacts.

## Workflow 3: Render The Final Report Inside Docker

From the cloned repository, after the required generated outputs exist:

```bash
docker compose run --rm report
```

This renders `reports/final_report.html` from the cloned working tree. The HTML
is generated and ignored by Git; `reports/final_report.qmd`, `_quarto.yml`,
required data, and canonical output inputs are committed.

The report service only validates inputs and invokes Quarto. It does not run
preprocessing, fixed experiments, optimization, or final-portfolio generation.
If an input is absent, the preflight lists every missing path and the applicable
explicit command. The report requires outputs from:

```bash
python -m strategy_development.local_implementation.reproduce
python -m strategy_development.local_implementation.run_fixed_15m_experiments
python -m strategy_development.local_implementation.optimization.run_all_optimizations
```

Some optional portfolio sections additionally use artifacts from:

```bash
python -m final_portfolio.run_report
```

For maintainers, the following convenience workflow regenerates report inputs
and renders the report. It is optional, includes optimization, and may take a
long time:

```bash
make docker-reproduce-report-full
```

## Repository Structure

```text
data/                         Committed raw and processed datasets
preprocessing/                Deterministic preprocessing utilities
strategy_development/         Reference strategies and authoritative local implementation
trade_dependency/             Trade autocorrelation analysis
final_portfolio/              Portfolio construction
outputs/                      Generated and canonical report inputs
reports/final_report.qmd      Final Quarto report source
tests/                        Offline tests
Dockerfile                    Reproduction image with Quarto installed
docker-compose.yml            Reproduction, report, test, and explicit heavy services
```

## Local Development

```bash
pip install -e ".[dev,report]"
pytest
python -m strategy_development.local_implementation.reproduce
docker compose config
```

Useful Make targets:

```bash
make test
make reproduce
make docker-reproduce
make docker-report
```

The project uses committed offline OHLCV data. It performs no live downloads in
the canonical reproduction path. Strategy transaction costs are centralized,
and optimization fits train data only, uses validation for selection, and
reserves test data for final out-of-sample evaluation.

## Publishing

After all local checks pass:

```bash
docker tag intraday-momentum-repro radek1715/intraday-momentum-repro:latest
docker push radek1715/intraday-momentum-repro:latest
docker rmi radek1715/intraday-momentum-repro:latest
docker pull radek1715/intraday-momentum-repro:latest
docker inspect radek1715/intraday-momentum-repro:latest --format "{{json .Config.Cmd}}"
docker run --rm radek1715/intraday-momentum-repro:latest
```

## Team Members

- Eryk Szatan
- Kacper Lambert
- Natalia Kowalczyk
- Radoslaw Szostak

AI usage is disclosed in [AI_USAGE.md](AI_USAGE.md).
