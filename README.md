# Intraday Momentum Reproduction And Extension

This project was developed for the **Reproducible Research** course at the University of Warsaw.

The goal is to locally reproduce and extend five QuantConnect-style intraday momentum strategies using committed offline data and deterministic outputs. QuantConnect and Lean are referenced only as the original implementation source; neither is required at runtime.

The repository contains:

- deterministic preprocessing,
- local strategy implementations,
- optimization using NES and CMA-ES,
- portfolio construction,
- Quarto reporting,
- Docker-based reproducibility.

All experiments use committed offline OHLCV datasets. No live downloads are performed in the canonical reproducibility pipeline.

---

# Workflow 1 – Run the prebuilt Docker image (recommended)

The fastest way to verify reproducibility is to use the prebuilt Docker image.

```bash
docker pull radek1715/intraday-momentum-repro:latest
docker run --rm radek1715/intraday-momentum-repro:latest
```

The image executes exactly:

```bash
python -m strategy_development.local_implementation.reproduce
```

This command:

- reproduces the baseline results,
- generates deterministic outputs,
- does **not** render Quarto,
- does **not** start Jupyter,
- does **not** run optimization,
- does **not** download any data.

---

# Workflow 2 – Clone the repository and reproduce everything locally

Clone the repository:

```bash
git clone https://github.com/Radzi000/RR_Szatan_Lambert_Kowalczyk_Szostak RR
cd RR
```

Run the canonical reproducibility pipeline:

```bash
docker compose up --build reproduce
```

The command generates the lightweight deterministic outputs inside the bind-mounted `outputs/` directory.

Unlike previous versions, the reproduce pipeline only overwrites files owned by the lightweight reproduction workflow and **never removes optimization outputs, fixed-15-minute outputs, portfolio outputs, or other report inputs**.

---

# Workflow 3 – Verify report inputs

Before rendering the report, verify that all required generated outputs exist.

```bash
python scripts/check_report_inputs.py
```

Expected output:

```text
Report preflight passed: all required generated outputs exist.
```

If any required files are missing, the script reports exactly which files are absent and which explicit command should be run.

No preprocessing, optimization, or portfolio generation is started automatically.

---

# Workflow 4 – Generate the final Quarto report

Render the report entirely inside Docker.

```bash
docker compose run --rm report
```

This generates:

```text
reports/final_report.html
```

The rendered HTML is intentionally ignored by Git.

The report source (`reports/final_report.qmd`), `_quarto.yml`, committed datasets, and all canonical report inputs remain version controlled.

---

# Required report inputs

The Quarto report requires outputs produced by the following pipelines:

```bash
python -m strategy_development.local_implementation.reproduce

python -m strategy_development.local_implementation.run_fixed_15m_experiments

python -m strategy_development.local_implementation.optimization.run_all_optimizations
```

Some optional portfolio sections additionally use:

```bash
python -m final_portfolio.run_report
```

Heavy optimization is **never executed automatically** by either:

```bash
docker run
```

or

```bash
docker compose run --rm report
```

---

# Repository structure

```text
data/                         Committed raw and processed datasets

preprocessing/                Deterministic preprocessing

strategy_development/         Local strategy implementations,
                              backtester, optimization,
                              reference QuantConnect strategies

trade_dependency/             Trade dependency analysis

final_portfolio/              Portfolio construction

outputs/                      Generated deterministic outputs

reports/                      Quarto report

tests/                        Offline test suite

Dockerfile                    Docker image definition

docker-compose.yml            Docker services

Makefile                      Automation commands

.github/                      GitHub Actions CI workflow
```

---

# Local development

Install development dependencies:

```bash
pip install -e ".[dev,report]"
```

Run tests:

```bash
pytest
```

Run lightweight reproduction:

```bash
python -m strategy_development.local_implementation.reproduce
```

Validate Docker configuration:

```bash
docker compose config
```

Useful Make targets:

```bash
make test

make reproduce

make docker-reproduce

make docker-report

make docker-reproduce-report-full
```

The last command performs a complete regeneration of optimization outputs and may require a long execution time.

---

# Maintainer Notes (Docker Hub)

The following commands are only required when publishing a new Docker image.

Build the image:

```bash
docker build -t intraday-momentum-repro .
```

Tag the image:

```bash
docker tag intraday-momentum-repro radek1715/intraday-momentum-repro:latest
```

Push to Docker Hub:

```bash
docker push radek1715/intraday-momentum-repro:latest
```

Verify the published image:

```bash
docker rmi radek1715/intraday-momentum-repro:latest

docker pull radek1715/intraday-momentum-repro:latest

docker inspect radek1715/intraday-momentum-repro:latest --format "{{json .Config.Cmd}}"

docker run --rm radek1715/intraday-momentum-repro:latest
```

The default command of the published image must always be:

```bash
python -m strategy_development.local_implementation.reproduce
```

---

# Reproducibility

This repository follows a deterministic reproducibility workflow:

- committed offline datasets,
- deterministic preprocessing,
- explicit train / validation / test split,
- fixed random seeds,
- Docker-based execution,
- GitHub Actions continuous integration,
- Quarto-generated final report,
- no live data downloads,
- no cloud dependencies,
- no QuantConnect runtime dependency.

---

# Team Members

- Eryk Szatan
- Kacper Lambert
- Natalia Kowalczyk
- Radosław Szostak

AI usage is documented in **AI_USAGE.md**.