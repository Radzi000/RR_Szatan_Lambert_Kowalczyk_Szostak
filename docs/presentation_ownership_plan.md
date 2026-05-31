# Presentation Ownership Plan

## A. Executive Summary

The presentation should flow from project story to reproducibility infrastructure, then to data, strategies, optimization results, portfolio construction, reporting, and tests. Radek opens and owns the research story plus strategy/backtest/optimization mechanics. Eryk and Natalka jointly cover Docker, CI, environment control, and repository automation, with Eryk also owning the reproducible data contract. Kacper owns results interpretation plus tests, report-generation commands, and live-demo flow. Natalka owns final portfolio, visuals, and Quarto reporting.

## B. Suggested 20-Minute Presentation Timeline

| Time | Speaker | Topic | Goal |
|---|---|---|---|
| 0:00-2:00 | Radek | Project summary and story | Explain what was reproduced, what was extended, and why local reproducibility matters. |
| 2:00-5:00 | Eryk i Natalka | Repository, Docker, CI, and environment control | Show how `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `Makefile`, CI, and root automation support reproducibility. |
| 5:00-8:00 | Eryk | Data and preprocessing contract | Explain committed data, no live downloads, schema, manifests, train/validation/test splits, and deterministic preprocessing. |
| 8:00-12:00 | Radek | Strategy implementation, backtesting, costs, optimization | Explain local strategy classes, backtest engine, centralized transaction costs, NES/CMA-ES, and look-ahead controls. |
| 12:00-15:00 | Kacper | Results and optimized strategies | Present baseline vs optimized results, train/validation behavior, and limitations. |
| 15:00-17:30 | Natalka | Final portfolio, visuals, Quarto report | Explain equal-weight, Kelly-style, Markowitz, generated figures, and report source. |
| 17:30-19:00 | Kacper | Tests, report generation, and demo commands | Show `pytest`, Quarto render, and generated outputs. |
| 19:00-20:00 | All | Professor questions | Eryk and Natalka answer Docker/reproducible environment questions; Eryk answers data reproducibility; Radek answers strategy/optimization; Kacper answers results/tests/demo; Natalka answers portfolio/reporting. |

## C. 4-Person Split

### Person 1: Radek - Project Story, Strategies, Backtesting, Costs, And Optimization

**Owned files/folders**

- `README.md` project-story sections
- `AGENTS.md` research and reproducibility rules
- `strategy_development/`
- `strategy_development/README.md`
- `strategy_development/taken_strategies/`
- `strategy_development/local_implementation/`
- `strategy_development/local_implementation/strategies/`
- `strategy_development/local_implementation/backtest/`
- `strategy_development/local_implementation/data/provider.py`
- `strategy_development/local_implementation/costs.py`
- `strategy_development/local_implementation/strategy_specs.py`
- `strategy_development/local_implementation/reproduce.py`
- `strategy_development/local_implementation/run_fixed_15m_experiments.py`
- `strategy_development/local_implementation/optimization/`

**Presentation responsibilities**

- Open with the 1-minute project summary:
  - reproduced five QuantConnect-style intraday momentum strategies,
  - rewrote them locally in Python,
  - extended them to a deterministic multi-asset research pipeline,
  - kept the final reproduction offline, Dockerized, and independent of QuantConnect.
- Explain the full pipeline at a high level: `data -> preprocessing -> strategy_development -> optimization -> final_portfolio -> outputs -> reports`.
- Explain the original `taken_strategies/` files are reference-only.
- Explain the local implementation is authoritative.
- Explain key modules:
  - data provider/loader,
  - backtest engine,
  - strategy base class,
  - Strategy0 through Strategy4,
  - centralized cost model,
  - optimization runner,
  - optimization metrics.
- Explain the five strategy variants:
  - Strategy0 / Baseline,
  - Strategy1 / Asymmetric Intervals,
  - Strategy2 / EMA Filter,
  - Strategy3 / Exit Confirmation,
  - Strategy4 / EMA + Confirmation.
- Explain transaction-cost awareness:
  - costs are centralized in `costs.py`,
  - results are net of costs unless explicitly labelled gross,
  - optimization objective uses cost-adjusted train net Sharpe.
- Explain optimization:
  - NES for Strategy0, Strategy1, Strategy2,
  - CMA-ES for Strategy3, Strategy4,
  - train-only fitting,
  - validation-only verification/selection,
  - test/OOS not used during tuning.

**Exact professor questions Radek should answer**

- What did you reproduce?
- What did you extend?
- Why is QuantConnect not required at runtime?
- Where are the strategy classes?
- Where is the backtest engine?
- How do the five strategies differ?
- How are transaction costs handled?
- How are NES and CMA-ES used?
- How do you avoid look-ahead bias in optimization?
- Why is full optimization separate from canonical Docker reproduction?

**Suggested demo commands**

```bash
python -m strategy_development.local_implementation.reproduce
python -m strategy_development.local_implementation.run_fixed_15m_experiments
python -m strategy_development.local_implementation.optimization.run_all_optimizations --smoke
```

**Expected slide topics**

- "What we reproduced and extended."
- "Reference QuantConnect files vs local Python implementation."
- "Backtest engine and strategy classes."
- "Centralized transaction costs."
- "Train-only optimization and validation selection."

**Things Radek should avoid saying**

- Do not say QuantConnect is required.
- Do not say validation data is used for optimizer fitting.
- Do not say test data was used unless showing a specific final test/OOS output.
- Do not present smoke-mode optimization as the full research optimization.

### Person 2: Eryk - Data Contract And Shared Reproducibility Infrastructure

**Owned files/folders**

- `data/`
- `data/README.md`
- `data/processed/`
- `preprocessing/`
- `preprocessing/README.md`
- `preprocessing/build_data_manifest.py`
- `preprocessing/make_global_splits.py`
- `preprocessing/materialize_processed_data.py`
- `preprocessing/validate_schema.py`
- `preprocessing/loader.py`
- `preprocessing/splitter.py`
- `preprocessing/export_unified.py`
- `preprocessing/export_splits.py`
- `docs/strategy_data_audit.md`
- `docs/workstream_c_readiness_audit.md`
- shared with Natalka: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `Makefile`, `.github/workflows/ci.yml`

**Presentation responsibilities**

- Co-present repository, Docker, CI, and environment control with Natalka from 2:00-5:00.
- Own the data and preprocessing section from 5:00-8:00.
- Explain committed data and why the pipeline avoids live downloads.
- Explain raw data folders:
  - `data/1day/`,
  - `data/5min/`,
  - `data/15min/equities/`,
  - `data/15min/commodities/`,
  - `data/15min/crypto/`.
- Explain deterministic processed data:
  - `data/processed/manifests/data_manifest.json`,
  - `data/processed/splits/global_time_splits.json`,
  - `data/processed/unified/*.csv`,
  - `data/processed/splits/csv/*.csv`.
- Explain the OHLCV schema: `timestamp, open, high, low, close, volume`.
- Explain train/validation/test split discipline:
  - train for optimizer fitting,
  - validation for parameter/model selection,
  - test reserved for final out-of-sample evaluation.
- Explain why schema validation, manifests, and split files matter for reproducible research.
- In the Docker/CI section, explain how committed data and deterministic commands make the container meaningful.

**Exact professor questions Eryk should answer**

- Where is the data?
- How do you avoid live downloads?
- What is the schema?
- Where are train/validation/test splits?
- What is `data_manifest.json`?
- What is `global_time_splits.json?
- Why store processed data under `data/processed/`?
- What does `python -m preprocessing.materialize_processed_data` do?
- How does the data contract support Docker reproducibility?
- How did you branch/collaborate on data and preprocessing?

**Suggested demo commands**

```bash
python -m preprocessing.materialize_processed_data
python -m preprocessing.build_data_manifest
python -m preprocessing.make_global_splits
docker compose config
```

**Expected slide topics**

- "Committed data, no live downloads."
- "Raw to processed data contract."
- "Global train/validation/test splits."
- "Schema validation and manifests."
- "Data reproducibility plus environment reproducibility."

**Things Eryk should avoid saying**

- Do not say the project downloads fresh data during final reproduction.
- Do not say validation or test data is used for optimizer fitting.
- Do not overclaim final test/OOS results if only validation is being discussed.

### Person 3: Kacper - Results, Optimized Strategies, Tests, And Demo Flow

**Owned files/folders**

- `outputs/`
- `outputs/tables/`
- `outputs/figures/`
- `outputs/report/`
- `outputs_smoke/`
- `tests/`
- `tests/README.md`
- `tests/test_costs.py`
- `tests/test_fixed_15m_runner.py`
- `tests/test_optimization.py`
- `tests/test_preprocessing.py`
- `tests/test_reproduce.py`
- result-oriented report sections in `reports/final_report.qmd`

**Presentation responsibilities**

- Present baseline vs optimized results from 12:00-15:00.
- Explain train vs validation behavior and limitations.
- Explain which tables support claims:
  - `fixed_15m_strategy_summary.csv`,
  - `fixed_15m_train_validation_test_summary.csv`,
  - `verification_metrics_taken_strats.csv`,
  - `verification_metrics_our_strats.csv`,
  - `selected_params.csv`,
  - `train_validation_comparison.csv`,
  - `optimization_verification_metrics.csv`.
- Explain generated figures:
  - taken equity curves/drawdowns,
  - optimized train/validation equity curves,
  - optimized train/validation drawdowns,
  - optimization convergence,
  - train-validation Sharpe comparison.
- Explain why smoke outputs exist in `outputs_smoke/`.
- Own tests and demo commands from 17:30-19:00.
- Explain what `pytest` checks and why tests matter for reproducibility.
- Explain how to run the report generation commands in the correct order.

**Exact professor questions Kacper should answer**

- Which strategy performed best?
- Did optimization improve validation performance?
- What are the main limitations?
- What do the generated tables mean?
- Where are the charts?
- What does `pytest` cover?
- Why do tests matter for reproducibility?
- Why use smoke mode for a live demo?
- How can I reproduce the project from scratch?
- How can I render and open the report?

**Suggested demo commands**

```bash
pytest
python -m strategy_development.local_implementation.reproduce
python -m strategy_development.local_implementation.optimization.run_all_optimizations --smoke
quarto render reports/final_report.qmd
start reports/final_report.html
```

**Expected slide topics**

- "Taken vs optimized strategies."
- "Train vs validation behavior."
- "Optimization convergence and Sharpe comparison."
- "Tests as reproducibility checks."
- "Demo command checklist."

**Things Kacper should avoid saying**

- Do not claim full optimization was run live if using `--smoke`.
- Do not imply validation metrics are final test/OOS performance.
- Do not present generated outputs as hand-edited.

### Person 4: Natalka - Docker/CI Co-Owner, Final Portfolio, Quarto, And Visuals

**Owned files/folders**

- shared with Eryk: `Dockerfile`
- shared with Eryk: `docker-compose.yml`
- shared with Eryk: `.dockerignore`
- shared with Eryk: `.gitignore`
- shared with Eryk: `.pre-commit-config.yaml`
- shared with Eryk: `.github/workflows/ci.yml`
- shared with Eryk: `Makefile`
- `final_portfolio/`
- `final_portfolio/README.md`
- `final_portfolio/equal_weight.py`
- `final_portfolio/kelly.py`
- `final_portfolio/markowitz.py`
- `final_portfolio/run_report.py`
- `final_portfolio/portfolio_report.py`
- `final_portfolio/visuals/`
- `trade_dependency/`
- `reports/`
- `reports/final_report.qmd`
- `reports/workstream_c_optimization_report.qmd`
- `_quarto.yml`
- `AI_USAGE.md`
- `docs/`

**Presentation responsibilities**

- Co-present repository, Docker, CI, and environment control with Eryk from 2:00-5:00.
- Explain every major `Dockerfile` instruction:
  - `FROM python:3.11-slim`: compact Python base image,
  - `LABEL`: project metadata,
  - `ENV`: deterministic Python logging/runtime behavior and plotting backend,
  - `WORKDIR /app`: stable in-container project root,
  - `RUN apt-get ...`: build tools and timezone data,
  - `COPY . .`: copies versioned source into the image,
  - `pip install --no-cache-dir -e ".[dev]"`: installs the project package plus dev/test dependencies,
  - `CMD`: default reproduction command.
- Explain `docker-compose.yml` services:
  - `reproduce`,
  - `test`,
  - `shell`,
  - `optimization`,
  - `results`.
- Explain why Compose is easier than raw `docker run`.
- Explain `.dockerignore` and "do not put trash in a container":
  - exclude `.git`,
  - exclude caches,
  - exclude `outputs/`,
  - exclude `data_cache/`,
  - exclude virtualenvs and package metadata.
- Explain CI and pre-commit at a high level with Eryk.
- Explain final portfolio layer:
  - equal-weight allocation,
  - Kelly-style allocation,
  - Markowitz maximum-Sharpe allocation,
  - generated figures and report.
- Explain `trade_dependency/` and `final_portfolio/trade_dependency.py` as supporting analysis code.
- Explain Quarto:
  - `_quarto.yml` configures project rendering, HTML output, table of contents, code folding, and figure behavior,
  - `reports/final_report.qmd` reads generated CSVs/PNGs from `outputs/`,
  - rendered HTML is not committed because it is generated,
  - report generation is reproducible from source and outputs.
- Explain AI usage disclosure in `AI_USAGE.md`.

**Exact professor questions Natalka should answer**

- What does `Dockerfile` do?
- What base image is used?
- Why `WORKDIR`?
- Why `COPY`?
- Why `pip install`?
- What command is run?
- Why not put caches/generated outputs in the container?
- How does `.dockerignore` help?
- What does `docker-compose.yml` do?
- What services exist?
- Did you use dev containers?
- How could someone work interactively in Docker?
- What does Quarto do?
- Why not commit rendered HTML?
- What are the final portfolio methods?
- Where are generated visuals?
- What is `AI_USAGE.md`?

**Suggested demo commands**

```bash
docker compose up --build reproduce
docker compose run --rm shell
python -m final_portfolio.run_report
quarto render reports/final_report.qmd
```

**Expected slide topics**

- "Dockerfile and Compose walkthrough."
- "Clean build context with `.dockerignore`."
- "Final portfolio methods."
- "Generated visuals and Quarto source report."
- "Why rendered reports are ignored."

**Things Natalka should avoid saying**

- Do not say Docker guarantees profitable results; it controls the environment.
- Do not say CI runs full expensive optimization.
- Do not say rendered report files should be committed.
- Do not say VS Code dev containers were used. Say: "We did not rely on VS Code dev containers. Docker is used as a reproducible execution environment, not as the primary interactive development environment."

## D. Full Repository Coverage Table

| Path | Owner | Why it belongs to this owner | What to say about it |
|---|---|---|---|
| `.github/` | Eryk + Natalka | CI and automated reproducibility checks. | Contains GitHub Actions workflow definitions. |
| `.github/workflows/ci.yml` | Eryk + Natalka | Required professor topic. | Runs install, `pytest`, `docker compose config`, local reproduction, and Docker image build on push/PR. |
| `.git/` | Eryk + Natalka | Repository history and collaboration metadata. | Not presented in detail; mention feature branches, commits, and PR discipline. |
| `.pytest_cache/` | Natalka | Generated local test cache and build hygiene topic. | Should not be committed or copied into Docker. |
| `.quarto/` | Natalka | Generated Quarto cache. | Not committed; created by rendering and ignored. |
| `.dockerignore` | Natalka | Docker build hygiene. | Excludes `.git`, caches, virtualenvs, `outputs/`, `data_cache/`, and build artifacts from build context. |
| `.gitignore` | Natalka | Repository cleanliness. | Keeps generated outputs, rendered reports, caches, virtualenvs, and OS files out of Git. |
| `.pre-commit-config.yaml` | Natalka | Local quality gates. | Runs whitespace, YAML/TOML, large-file, Ruff lint, and Ruff format hooks. |
| `AGENTS.md` | Radek | Project rules and constraints. | Documents no QuantConnect runtime, no live downloads, relative paths, and cost centralization. |
| `AI_USAGE.md` | Natalka | Disclosure and academic transparency. | Explains AI assistance usage. |
| `Dockerfile` | Natalka + Eryk | Main reproducible environment definition. | Builds Python image, installs package dependencies, and defaults to reproduction command. |
| `Makefile` | Eryk + Natalka | Automation and reduced manual error. | Wraps test, preprocessing, optimization, report, Docker, and cleanup commands. |
| `README.md` | Radek | Main project story and reproduction guide. | Professor should be able to understand the project and reproduce it from README commands. |
| `_quarto.yml` | Natalka | Quarto report configuration. | Sets project title, HTML format, TOC, code folding, and rendered report sources. |
| `data/` | Eryk | Committed raw and processed data. | Offline inputs and deterministic processed data contract. |
| `data/README.md` | Eryk | Data documentation. | Explains data sources, structure, and reproducibility assumptions. |
| `data/1day/` | Eryk | Daily SPY input. | Used for daily context/baseline. |
| `data/5min/` | Eryk | 5-minute SPY input. | Used in canonical local reproduction. |
| `data/15min/` | Eryk | Cross-asset extension data. | Equities, commodities, and crypto 15-minute research extension. |
| `data/processed/` | Eryk | Deterministic preprocessing outputs. | Contains manifests, unified files, and split CSVs used by optimization. |
| `data_cache/` | Natalka | Local cache/trash. | Ignored; not part of canonical reproduction or Docker image. |
| `docs/` | Natalka | Supporting documentation and presentation plan. | Audit notes, restructuring plan, readiness notes, and this ownership plan. |
| `docs/presentation_ownership_plan.md` | Natalka | Presentation coordination artifact. | Assigns files, folders, demos, and professor questions. |
| `docs/repository_restructuring_plan.md` | Natalka | Documentation history. | Explains repository organization decisions. |
| `docs/strategy_data_audit.md` | Eryk | Data/strategy audit. | Supports data and strategy provenance discussion. |
| `docs/workstream_c_readiness_audit.md` | Eryk | Workstream C readiness. | Explains whether preprocessing/data are ready for optimization. |
| `final_portfolio/` | Natalka | Portfolio construction layer. | Equal-weight, Kelly-style, Markowitz, dependency analysis helpers, plots, and report generation. |
| `final_portfolio/equal_weight.py` | Natalka | Portfolio baseline. | Builds simple 1/N portfolio. |
| `final_portfolio/kelly.py` | Natalka | Kelly-style allocation. | Uses trade-level statistics and grid search. |
| `final_portfolio/markowitz.py` | Natalka | Markowitz allocation. | Uses rolling covariance/returns and maximum-Sharpe optimization. |
| `final_portfolio/run_report.py` | Natalka | Portfolio execution entry point. | Generates portfolio figures and markdown report from optimization outputs. |
| `final_portfolio/visuals/` | Natalka | Portfolio plotting. | Produces comparison, timeline, grid search, ACF, and drawdown charts. |
| `intraday_momentum.egg-info/` | Natalka | Generated package metadata. | Local install artifact; not presentation focus and should not drive reproducibility. |
| `outputs/` | Kacper | Generated canonical results. | Tables, figures, and generated markdown reports consumed by Quarto. |
| `outputs/tables/` | Kacper | Strategy/optimization metrics. | CSV outputs used for verification and report tables. |
| `outputs/figures/` | Kacper | Generated plots. | Equity curves, drawdowns, optimization charts, and portfolio visuals. |
| `outputs/report/` | Kacper | Generated markdown reports. | Reproducible artifacts, not manually edited. |
| `outputs_smoke/` | Kacper | Smoke optimization outputs. | Practical demonstration outputs for faster checks. |
| `preprocessing/` | Eryk | Deterministic data processing. | Builds manifests, validates schema, exports unified/split data. |
| `preprocessing/build_data_manifest.py` | Eryk | Manifest generation. | Creates machine-readable data provenance. |
| `preprocessing/make_global_splits.py` | Eryk | Split boundaries. | Creates train/validation/test split definitions. |
| `preprocessing/materialize_processed_data.py` | Eryk | Preprocessing entry point. | Runs manifest, splits, unified exports, and split CSV exports. |
| `preprocessing/validate_schema.py` | Eryk | Schema enforcement. | Verifies OHLCV contract. |
| `pyproject.toml` | Eryk + Natalka | Package/dependency configuration. | Defines install requirements, optional dev/report dependencies, Ruff, pytest, setuptools package discovery. |
| `reports/` | Natalka | Quarto report source. | Source report files only; rendered HTML ignored. |
| `reports/final_report.qmd` | Natalka | Final presentation report. | Reads generated tables/figures and renders reproducible HTML. |
| `reports/workstream_c_optimization_report.qmd` | Natalka | Optional optimization report. | Documents Workstream C optimization inputs/outputs. |
| `strategy_development/` | Radek | Strategy research code. | Reference strategies and authoritative local implementation. |
| `strategy_development/taken_strategies/` | Radek | Original downloaded reference strategies. | Preserved as reference-only QuantConnect-style files. |
| `strategy_development/local_implementation/` | Radek | Local authoritative implementation. | Backtest, strategies, costs, data provider, optimization, and reproduction scripts. |
| `strategy_development/local_implementation/backtest/` | Radek | Backtest engine. | Runs strategy logic over local OHLCV data. |
| `strategy_development/local_implementation/data/` | Radek | Strategy data provider. | Loads data for local backtests. |
| `strategy_development/local_implementation/optimization/` | Radek | NES/CMA-ES optimization. | Train-only search and validation verification. |
| `strategy_development/local_implementation/strategies/` | Radek | Strategy classes. | Strategy0 through Strategy4 and shared base code. |
| `strategy_development/local_implementation/visualization/` | Kacper | Strategy result plots. | Equity curves and drawdown plotting helpers used in results discussion. |
| `tests/` | Kacper | Automated correctness checks. | Offline tests for costs, preprocessing, fixed runner, optimization, and reproduction. |
| `tests/test_costs.py` | Kacper | Cost model tests. | Confirms centralized transaction-cost behavior. |
| `tests/test_preprocessing.py` | Kacper | Data pipeline tests. | Confirms preprocessing contract. |
| `tests/test_optimization.py` | Kacper | Optimization tests. | Confirms optimization behavior and guardrails. |
| `tests/test_reproduce.py` | Kacper | Reproduction tests. | Confirms canonical local reproduction outputs. |
| `tests/test_fixed_15m_runner.py` | Kacper | Fixed 15-minute runner tests. | Confirms cross-asset baseline output behavior. |
| `trade_dependency/` | Natalka | Supporting portfolio dependency analysis. | Explain as supporting analysis around trade autocorrelation/dependency, not core canonical reproduction. |

## E. Professor Question Map

| Likely question | Who answers | Short answer |
|---|---|---|
| What did you use GitHub Actions for? | Natalka + Eryk | CI installs the project, runs tests, validates Docker Compose, runs local reproduction, and builds the Docker image on push/PR. |
| Why does CI matter for reproducibility? | Eryk + Natalka | It automatically checks that a fresh environment can install, test, and reproduce expected outputs. |
| What exactly does CI check? | Natalka | `pytest`, `docker compose config`, `python -m strategy_development.local_implementation.reproduce`, and `docker compose build reproduce`. |
| What does `Dockerfile` do? | Natalka | It defines the reproducible Python environment, installs dependencies, copies code, and sets the default reproduction command. |
| What base image is used? | Natalka | `python:3.11-slim`, a compact official Python image. |
| Why Docker? | Eryk + Natalka | Docker fixes the runtime environment so the professor does not need to match the developers' local machines. |
| What does `docker-compose.yml` do? | Natalka | It defines repeatable services: `reproduce`, `test`, `shell`, `optimization`, and `results`. |
| Why Compose instead of raw Docker? | Natalka | Compose stores service commands, image name, build context, and mounted outputs in versioned YAML. |
| What does `Makefile` automate? | Eryk + Natalka | Installation, tests, preprocessing, fixed baseline, optimization, report rendering, Docker commands, and cleaning. |
| Why use a Makefile? | Eryk | It reduces manual command mistakes and gives stable command names for contributors. |
| What do pre-commits do? | Natalka | They catch formatting, YAML/TOML, whitespace, and large-file problems before commits. |
| What is `.dockerignore` for? | Natalka | It keeps caches, outputs, virtualenvs, `.git`, and build products out of Docker build context. |
| Did you use dev containers? | Natalka | We did not rely on VS Code dev containers. Docker is used as a reproducible execution environment, not as the primary interactive development environment. |
| How could someone work interactively in Docker? | Natalka | Use `docker compose run --rm shell`, which uses the configured shell service. |
| How did you branch/collaborate? | Eryk | Use feature branches, scoped commits, PRs, and ownership by workstream. |
| Where is the data? | Eryk | Raw data is under `data/`; processed deterministic data is under `data/processed/`. |
| How do you avoid live downloads? | Eryk | The canonical pipeline reads committed local CSVs and deterministic processed files only. |
| Where are train/validation/test splits? | Eryk | In `data/processed/splits/global_time_splits.json` and split CSVs under `data/processed/splits/csv/`. |
| How do you avoid look-ahead bias? | Eryk + Radek | Optimizers fit on train only; validation is used for selection; test is reserved and not used for tuning. |
| What was reproduced? | Radek | Five QuantConnect-style intraday momentum strategies preserved as references and rewritten locally. |
| Why no QuantConnect dependency? | Radek | QuantConnect files are reference-only; local Python code is authoritative and runs offline. |
| Where are the strategy classes? | Radek | `strategy_development/local_implementation/strategies/`. |
| Where is the backtest engine? | Radek | `strategy_development/local_implementation/backtest/engine.py`. |
| How are transaction costs handled? | Radek | Centralized in `strategy_development/local_implementation/costs.py` and applied inside backtests/optimization. |
| How are NES/CMA-ES used? | Radek | NES optimizes Strategy0-2; CMA-ES optimizes Strategy3-4; objective is train net Sharpe. |
| Why smoke optimization? | Kacper | It is deterministic and practical for demos/CI; full optimization is slower. |
| Which strategy performed best? | Kacper | Answer from the generated validation/result tables, not from memory. |
| Why Quarto? | Natalka | Quarto turns source plus generated tables/figures into a reproducible final HTML report. |
| Why not commit rendered report? | Natalka | HTML/PDF/DOCX are generated artifacts; committing source avoids stale reports and noisy diffs. |
| How does Quarto read outputs? | Natalka | `reports/final_report.qmd` reads CSV files from `outputs/tables/` and PNGs from `outputs/figures/`. |
| Where are final portfolio functions? | Natalka | `final_portfolio/equal_weight.py`, `kelly.py`, `markowitz.py`, and `run_report.py`. |
| Where are figures? | Kacper + Natalka | Strategy/result figures are in `outputs/figures/`; portfolio visuals are generated from `final_portfolio/`. |
| Where are tests? | Kacper | `tests/`. |
| How can I reproduce from scratch? | Kacper | Run `docker compose up --build reproduce`; for report generation, install report extras and run Quarto. |

## F. Recommended Demo Commands

Run these from repository root.

```bash
docker compose up --build reproduce
pytest
python -m preprocessing.materialize_processed_data
python -m strategy_development.local_implementation.reproduce
python -m strategy_development.local_implementation.optimization.run_all_optimizations --smoke
quarto render reports/final_report.qmd
start reports/final_report.html
```

Additional useful commands:

```bash
docker compose config
docker compose run --rm test
docker compose run --rm shell
python -m final_portfolio.run_report
```

## G. Safety Notes

- Full optimization may be slow. Use `--smoke` or the practical documented report command for a live demo.
- Rendered HTML should not be committed. The source file is `reports/final_report.qmd`.
- Docker Desktop must be running before Docker commands work on Windows.
- If Docker daemon is down, `docker info` or `docker compose up --build reproduce` will fail with a daemon/pipe connection error. Start Docker Desktop, wait for the Linux engine, then retry.
- `outputs/`, `.pytest_cache/`, `.quarto/`, `data_cache/`, `__pycache__/`, and virtualenvs are generated or local artifacts, not source code.
- Do not say the project requires QuantConnect, cloud APIs, live downloads, or manual notebook execution.
- Use validation language for optimization results unless a specific final test/OOS output is being discussed.
- Do not run full optimization live unless there is enough time.

## H. Final Recommendation

Use this ownership split:

- Radek: project opening, research story, strategy implementation, backtesting, transaction costs, and optimization mechanics.
- Eryk: data, preprocessing, manifests, schema, train/validation/test splits, and shared Docker/reproducibility explanation.
- Kacper: results, optimized strategy comparison, tests, report-generation commands, and live-demo flow.
- Natalka: Dockerfile/docker-compose/CI co-owner, final portfolio, visuals, Quarto report, generated-report hygiene, and AI disclosure.

This split matches the revised timeline and keeps reproducibility strongly covered by two people: Eryk for deterministic data contracts and Natalka for Docker/CI/environment control, with Kacper also prepared to run the reproducibility/demo commands.
