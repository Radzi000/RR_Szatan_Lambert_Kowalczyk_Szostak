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

The prebuilt image contains the committed optimization outputs and renders the
final Quarto report. It does not run preprocessing, training, fixed experiments,
NES, CMA-ES, or any other optimization.

```bash
docker pull radek1715/intraday-momentum-repro:latest
docker run --rm \
  -v "${PWD}/reports:/app/reports" \
  radek1715/intraday-momentum-repro:latest
```

Windows PowerShell uses the equivalent bind mount:

```powershell
docker run --rm `
  -v "${PWD}/reports:/app/reports" `
  radek1715/intraday-momentum-repro:latest
```

The image first runs `python scripts/check_report_inputs.py`. If preflight
passes, it runs `quarto render reports/final_report.qmd`. The bind mount exports
the generated `reports/final_report.html` directly to the host directory.

If an input is missing, preflight lists the missing files and the explicit
commands that generate them, then exits without regenerating anything.

After the run, open the generated report in a browser. The command depends on
your operating system:

```bash
# macOS
open reports/final_report.html

# Linux
xdg-open reports/final_report.html
```

```powershell
# Windows (PowerShell / CMD)
start reports\final_report.html
```

On macOS and Linux use forward slashes (`/`); `start` and backslash paths work
only on Windows.

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
docker run --rm -v "${PWD}/reports:/app/reports" radek1715/intraday-momentum-repro:latest
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

make docker-publish

make docker-reproduce-report-full
```

The last command performs a complete regeneration of optimization outputs and may require a long execution time.

---

# Maintainer Notes (Docker Hub)

The following commands are only required when publishing a new Docker image.
Create or select a Buildx builder:

```bash
docker buildx create --use --name rr-builder || docker buildx use rr-builder
```

Build and push both supported platforms under one Docker Hub tag:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t radek1715/intraday-momentum-repro:latest \
  --push .
```

The equivalent convenience target is:

```bash
make docker-publish
```

Buildx creates a multi-architecture manifest under the single tag. Docker then
selects the correct image automatically: Intel and AMD machines receive the
`linux/amd64` image, while Apple Silicon Macs receive the `linux/arm64` image.

Verify the published image:

```bash
docker manifest inspect radek1715/intraday-momentum-repro:latest

docker pull radek1715/intraday-momentum-repro:latest

docker inspect radek1715/intraday-momentum-repro:latest --format "{{json .Config.Cmd}}"

docker run --rm \
  -v "${PWD}/reports:/app/reports" \
  radek1715/intraday-momentum-repro:latest
```

The manifest output must contain both `linux/amd64` and `linux/arm64`. Neither
platform should require an explicit `--platform` option when pulling or running.

The default command of the published image must validate the committed report
inputs and render:

```bash
reports/final_report.html
```

The lightweight developer reproduction remains available through
`docker compose up --build reproduce` and `make reproduce`.

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
