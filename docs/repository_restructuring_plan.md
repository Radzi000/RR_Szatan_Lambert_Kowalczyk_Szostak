# Repository Restructuring Plan

This planning document predates the cleanup that moved the working local implementation to
`strategy_development/local_implementation/`. It is kept as historical design context, but
the repository root and README now reflect the implemented structure.

## 1. Executive Recommendation

### Recommendation

Do not do a big-bang restructure. The repository now has a verified deterministic baseline:

```bash
docker compose up --build reproduce
```

That baseline is more valuable than a cleaner-looking tree. The safest plan is staged migration with backward-compatible wrappers and tests at every step.

### Should we restructure immediately?

- Not aggressively.
- Yes for documentation, manifests, and skeleton directories.
- No for moving the working package or changing Docker entry points until stronger tests exist.

### Safest staged migration plan

1. Freeze and protect the current Docker baseline.
2. Add planning docs and data manifests.
3. Add missing skeleton modules in new conceptual areas without moving working code.
4. Introduce preprocessing and split-generation modules alongside the current package.
5. Expand the pipeline to 15-minute cross-asset experiments.
6. Only then consider moving or wrapping code if the package layout still feels confusing.

### What should never be moved until tests are stronger?

- `intraday_momentum/`
- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- the current `python -m intraday_momentum.reproduce` entry point
- current committed baseline data paths used by `reproduce.py`

## 2. Proposed Final Repository Tree

```text
RR/
  data/
    1day/
    5min/
    15min/
      equities/
      commodities/
      crypto/
    processed/
      manifests/
      splits/
    metadata/
      checksums/
      schemas/
      sessions/
    README.md

  preprocessing/
    __init__.py
    load_raw_data.py
    normalize_schema.py
    validate_schema.py
    sessionize_assets.py
    make_global_splits.py
    build_data_manifest.py

  intraday_momentum/
    data/
    strategies/
    backtest/
    optimization/
    visualization/
    reproduce.py
    __init__.py

  strategy_development/
    README.md
    taken_strategies/
    local_experiments/
      configs/
      fixed_params/
      tuned_params/
      regime_aware/

  trade_dependency/
    __init__.py
    README.md
    regimes.py
    volatility_regimes.py
    seasonality.py
    time_of_day.py
    day_of_week.py
    trade_sequences.py

  final_portfolio/
    __init__.py
    README.md
    equal_weight.py
    kelly.py
    markowitz.py
    portfolio_report.py

  outputs/
    tables/
    figures/
    report/
    manifests/

  notebooks/
    exploratory/

  tests/
    test_reproduce.py
    test_data_schema.py
    test_splits.py
    test_strategy_smoke.py
    test_outputs.py

  docs/
    index.rst
    getting_started.rst
    strategy_data_audit.md
    repository_restructuring_plan.md

  Dockerfile
  docker-compose.yml
  Makefile
  pyproject.toml
  README.md
  AI_USAGE.md
```

### Core structural principle

- Keep `intraday_momentum/` as the working installable package.
- Use `strategy_development/` for reference logic and experiment organization.
- Use `preprocessing/`, `trade_dependency/`, and `final_portfolio/` as future research modules.
- Treat QuantConnect as source/reference only. No active integration.

## 3. Current-To-Final Mapping

| Current path | Current role | Proposed path | Action | Reason | Risk | Priority |
|---|---|---|---|---|---|---|
| `.git/` | Git metadata | same | keep as is | repository control | high | protect |
| `.pytest_cache/` | generated cache | ignored/generated only | keep generated, not structured content | not source | none | low |
| `data/` | committed reproducible inputs | `data/` | keep but expand/document | already canonical for reproducible data | medium | high |
| `data/1day/` | baseline daily SPY inputs | `data/1day/` or `data/raw/1day/` later | keep but document | needed by current pipeline | low | high |
| `data/5min/` | baseline SPY 5-minute inputs | `data/5min/` or `data/raw/5min/` later | keep but document | current faithful baseline | low | high |
| `data/15min/` | extension research inputs | `data/15min/` | keep but normalize later | main future cross-asset layer | low | high |
| `data/15min/equities/` | 15m equity files | same | keep but rename files later if needed | useful research data | medium | high |
| `data/15min/commodities/` | 15m commodity ETF files | same | keep but rename files later if needed | useful research data | medium | high |
| `data/15min/crypto/` | 15m crypto files | same | keep but sessionize/document later | useful research data | medium | high |
| `data/spy_1m_2017_2021.csv.gz` | archived reference dataset | `data/archive/` or `data/raw/reference/` later | keep but document as archival | not used by current pipeline, may be useful for fidelity checks | low | medium |
| `data/README.md` | current data doc | `data/README.md` | keep but expand | should become full data contract | low | high |
| `data_cache/` | local generated cache | generated only | keep ignored; do not make canonical | runtime convenience, not reproducible input | low | low |
| `docs/` | documentation root | `docs/` | keep | standard docs location | low | high |
| `docs/index.rst` | Sphinx landing page | same | keep but update later | docs entry point | low | medium |
| `docs/getting_started.rst` | onboarding doc, partly stale | same | keep but rewrite later | still useful, but currently references old workflow details | low | high |
| `docs/api/` | package API docs | same | keep | helpful if package remains canonical | low | medium |
| `docs/strategy_data_audit.md` | strategy/data audit | same | keep | useful design input | none | high |
| `docs/repository_restructuring_plan.md` | restructuring plan | same | keep | implementation roadmap | none | high |
| `final_portfolio/` | placeholder top-level concept | `final_portfolio/` | keep but convert into package later | matches desired pipeline story | low | medium |
| `intraday_momentum/` | working local package and canonical pipeline | `intraday_momentum/` | keep as is for now | lowest breakage path | high if moved | highest |
| `intraday_momentum/reproduce.py` | current deterministic entry point | same | keep stable | canonical Docker pipeline | high | highest |
| `intraday_momentum/data/` | current loader layer | same now, later coordinate with `preprocessing/` | keep | working package code | medium | high |
| `intraday_momentum/strategies/` | local strategy rewrites | same now | keep | core research code | high | highest |
| `intraday_momentum/backtest/` | local backtester | same now | keep | current engine used in Docker pipeline | high | highest |
| `intraday_momentum/optimization/` | current tuner code | same now | keep but expand later | natural home for NES/CMA-ES if package remains central | medium | high |
| `intraday_momentum/evaluation/` | near-empty placeholder | either populate or merge later | keep but document as incomplete | not harmful, but conceptually underdeveloped | low | medium |
| `intraday_momentum/visualization/` | output plotting layer | same | keep | already tied to outputs | low | high |
| `notebooks/` | exploratory work | `notebooks/exploratory/` later | keep but demote | should remain clearly non-canonical | low | medium |
| `outputs/` | generated artifacts | `outputs/` | keep but extend with `manifests/` | canonical generated results path | low | high |
| `outputs/tables/` | generated tables | same | keep | already canonical | low | high |
| `outputs/figures/` | generated figures | same | keep | already canonical | low | high |
| `outputs/report/` | generated report | same | keep | already canonical | low | high |
| `strategy_development/` | reference/research umbrella | same | keep but clarify purpose | name matches desired project story | low | high |
| `strategy_development/taken_strategies/` | preserved original QC-style files | same | keep immutable | original source/reference must remain preserved | low | highest |
| `strategy_development/our_strategies/` | empty ambiguous placeholder | `strategy_development/local_experiments/` or delete later | keep for now, replace later | current name duplicates `intraday_momentum` concept and causes confusion | low | medium |
| `tests/` | current smoke tests | `tests/` | keep and expand | critical guardrails before any move | low | highest |
| `tests/test_reproduce.py` | current end-to-end smoke coverage | same | keep and extend | current safety net | low | highest |
| `trade_dependency/` | placeholder top-level concept | `trade_dependency/` | keep but convert to package later | matches desired pipeline story | low | medium |
| `.dockerignore` | Docker build context filter | same | keep but revisit after data/process reorg | current build context depends on it | medium | high |
| `.gitignore` | repo ignore rules | same | keep but evolve | needed as data/output structure grows | low | high |
| `.pre-commit-config.yaml` | formatting/lint hooks | same | keep | basic code hygiene | low | medium |
| `AI_USAGE.md` | AI disclosure | same | keep and expand later | course requirement | low | high |
| `docker-compose.yml` | canonical service entry points | same | keep stable | core grading interface | high | highest |
| `Dockerfile` | canonical Docker build | same | keep stable | core grading interface | high | highest |
| `Makefile` | local convenience commands | same | keep stable | secondary user interface | medium | high |
| `pyproject.toml` | packaging, deps, pytest, ruff | same | keep stable, update carefully later | central to package identity | high | highest |
| `README.md` | canonical repo front page | same | keep but expand later | grader’s first interface | low | highest |

### Important nested items not above

| Current path | Action | Notes |
|---|---|---|
| `intraday_momentum/backtest/__main__.py` | keep | preserve compatibility for legacy module entry |
| `intraday_momentum/__init__.py` | keep | stable package identity |
| `docs/_static/` and `docs/_templates/` | keep | standard Sphinx support dirs |
| `__pycache__/` directories | treat as generated only | never part of final structure |

### Missing current area

| Missing path | Future action | Reason |
|---|---|---|
| `preprocessing/` | create later as new package/module area | needed to make data -> preprocessing -> strategy pipeline visually obvious |

## 4. Pipeline Design

### Intended global pipeline

1. Data inventory
2. Preprocessing and schema validation
3. Global time split `70 / 15 / 15`
4. Fixed-parameter local strategy runs
5. Train optimization with NES/CMA-ES
6. Validation-based selection
7. OOS test evaluation
8. Trade dependency analysis
9. Final portfolio construction
10. Report and output generation

### Step-by-step design

| Step | Input folder | Output folder | Script/module location | Reproducibility constraints | Tests needed |
|---|---|---|---|---|---|
| 1. Data inventory | `data/` | `data/metadata/` | `preprocessing/build_data_manifest.py` | checksums, row counts, schema summary, no path hardcoding | manifest and checksum tests |
| 2. Schema validation | `data/1day`, `data/5min`, `data/15min` | `data/processed/` or validated raw manifests | `preprocessing/validate_schema.py`, `normalize_schema.py` | fixed schema, timezone standard, deterministic normalization | schema tests |
| 3. Global splits | validated data | `data/processed/splits/` | `preprocessing/make_global_splits.py` | split dates fixed by config, no leakage | split determinism tests |
| 4. Fixed-parameter strategies | split train/val/test data | `outputs/tables/`, `outputs/figures/` | `intraday_momentum.reproduce` or later experiment runner | seed fixed, no live downloads, no notebooks | smoke strategy tests |
| 5. Train optimization | train split only | `outputs/tables/optimization/` or `outputs/manifests/` | `intraday_momentum.optimization` or wrapper scripts | train only, seeded optimizers, config logged | optimization config tests |
| 6. Validation selection | train outputs + validation data | `outputs/tables/model_selection/` | strategy experiment module | no test leakage | selection tests |
| 7. OOS evaluation | selected models + test split | `outputs/tables/oos/`, `outputs/figures/oos/` | strategy experiment module | test untouched until final eval | OOS smoke tests |
| 8. Trade dependency | trade logs and test results | `outputs/tables/dependency/`, `outputs/figures/dependency/` | `trade_dependency/` | deterministic feature construction | analysis smoke tests |
| 9. Portfolio construction | OOS strategy return streams | `outputs/tables/portfolio/`, `outputs/figures/portfolio/` | `final_portfolio/` | use train/validation stats only for weights where required | portfolio tests |
| 10. Final report | all prior outputs | `outputs/report/`, `outputs/manifests/` | report generator module | stable filenames, manifest update | output existence tests |

## 5. Strategy Architecture Recommendation

### Options evaluated

#### A. Keep `intraday_momentum/` as package

Pros:
- zero immediate breakage,
- already wired into Docker, tests, `pyproject.toml`, and README,
- package structure already separates strategies, data, backtest, optimization, and visualization cleanly.

Cons:
- less intuitive than a top-level `strategy_development/` story if not documented well.

Assessment:
- Best current choice.

#### B. Move code under `strategy_development/local_strategies/`

Pros:
- visually closer to the conceptual research story.

Cons:
- likely breaks package imports, editable install behavior, Docker, tests, and docs,
- increases migration risk for little immediate reproducibility gain.

Assessment:
- Not recommended now.

#### C. Move to `src/intraday_momentum/`

Pros:
- conventional Python packaging layout.

Cons:
- requires package and Docker changes,
- pure engineering cleanup, not a research necessity.

Assessment:
- Possible much later, only with strong tests and only if package hygiene becomes a real problem.

#### D. Rename package

Assessment:
- Not recommended. Renaming would introduce maximum churn with minimal research benefit.

### Best recommendation

Keep `intraday_momentum/` as the installable package.

Clarify roles instead of moving code:

- `intraday_momentum/` = executable local implementation
- `strategy_development/taken_strategies/` = preserved original source/reference
- future `strategy_development/local_experiments/` = experiment configs, comparison tables, non-package research scaffolding

If the user still wants a more intuitive conceptual structure later, add compatibility wrappers and documentation first. Do not move the package until:

- at least import tests,
- strategy smoke tests,
- output smoke tests,
- and Docker reproduce tests

all pass after each step.

## 6. Data Architecture Recommendation

### Current layout assessment

Current strengths:
- clear separation by frequency,
- committed deterministic baseline data exists,
- 15-minute cross-asset extension data is already present.

Current weaknesses:
- naming conventions are inconsistent:
  - equities: `AAPL_15mins_2016-02-26_2026-03-01.csv`
  - commodities: `COMMODITIES_GLD_15m.csv`
  - crypto: `BTCUSDT.csv`
- schema appears inconsistent:
  - some files use `date` lowercase,
  - baseline files use `Datetime` or `Date`,
  - timezone strings differ,
  - crypto is 24/7 while equities are session-based.

### Recommended final raw data layout

Keep raw committed data under:

```text
data/
  1day/
  5min/
  15min/
    equities/
    commodities/
    crypto/
```

This is already understandable and should not be broken now.

### Recommended processed data layout

Add later:

```text
data/processed/
  normalized/
  sessionized/
  splits/
  manifests/
```

### Recommended metadata layout

Add later:

```text
data/metadata/
  checksums/
  schemas/
  sessions/
  assets.csv
```

### Recommended file naming convention

Standardize later to something like:

- equities: `AAPL_15m.csv`
- commodities: `GLD_15m.csv`
- crypto: `BTCUSDT_15m.csv`
- daily: `SPY_1d.csv`
- baseline 5m: `SPY_5m.csv`

Keep asset class in folder path, not in file prefix.

### Recommended schema standard

Normalize all datasets later to:

- timestamp column name: `timestamp`
- columns:
  - `timestamp`
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume`
- plus metadata tracked separately:
  - `asset`
  - `asset_class`
  - `frequency`
  - `timezone`
  - `session_type`

### Timezone and session standard

Recommended:

- equities and commodity ETFs:
  - store or normalize to `US/Eastern`
  - regular session only unless extended-hours use is intentional
- crypto:
  - normalize to UTC internally or document a chosen canonical timezone
  - explicitly define artificial session boundaries for strategy logic

### Train / validation / test split files

Add deterministic split manifests later:

```text
data/processed/splits/
  global_split_boundaries.json
  assets_train.csv
  assets_validation.csv
  assets_test.csv
```

### Checksums

Every committed raw data file should eventually appear in a checksum manifest.

## 7. Outputs Architecture

### Final outputs layout

Recommended final generated layout:

```text
outputs/
  tables/
  figures/
  report/
  manifests/
```

### What should be committed

Commit:
- directory skeletons with `.gitkeep`,
- optionally one canonical final report snapshot if course expectations require visible results in GitHub,
- small stable summary tables if you want the repo browser to show final outputs immediately.

Regenerate automatically:
- plots,
- manifests,
- derived strategy tables,
- OOS comparison artifacts,
- dependency-analysis artifacts,
- portfolio artifacts.

### Guideline

If an output is cheap to regenerate and not needed for GitHub browsing, prefer regeneration. If a final small summary table materially helps the grader browse results without running Docker first, committing it is acceptable as long as it is documented as generated.

## 8. Tests Required Before And After Refactor

### Current minimum tests to preserve

- package import smoke test
- committed data load test
- reproduction pipeline output existence test

### Required additions before any real move

- import tests for all package submodules
- data schema tests for 1day, 5min, and 15min assets
- split determinism tests
- one-strategy smoke test on baseline SPY
- one-strategy smoke test on a 15-minute asset
- output manifest tests
- checksum consistency tests
- Docker reproduce smoke test in CI or documented local verification

### After any move/wrapper stage

- re-run:
  - `pytest`
  - `docker compose up --build reproduce`
  - output existence checks
  - manifest checks

## 9. README / Documentation Plan

README should eventually tell this story:

- what was taken from the upstream MIT/QuantConnect-style source,
- what is reproduced locally,
- what is extended beyond SPY,
- that QuantConnect is not an active dependency,
- that the canonical workflow is Docker,
- that 5-minute SPY is the faithful local baseline,
- that 15-minute cross-asset data is the main extension layer,
- where train/validation/test fits,
- where optimization, trade dependency, and portfolios fit,
- where AI usage is disclosed,
- what limitations remain.

Docs should split responsibilities:

- `README.md`: grader-facing overview and commands
- `docs/getting_started.rst`: local dev and docs build details
- `docs/strategy_data_audit.md`: strategy logic and data-requirement reasoning
- `docs/repository_restructuring_plan.md`: migration roadmap

## 10. Cleanup Plan

### Safe to keep

- `intraday_momentum/`
- `data/`
- `outputs/`
- `tests/`
- `docs/`
- `README.md`
- `AI_USAGE.md`
- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `pyproject.toml`
- `strategy_development/taken_strategies/`

### Keep but document better

- `notebooks/`
- `intraday_momentum/evaluation/`
- `data/spy_1m_2017_2021.csv.gz`

### Should be archived or renamed later

- `strategy_development/our_strategies/`

### Placeholder areas to build out later

- `trade_dependency/`
- `final_portfolio/`

### Generated or non-canonical areas

- `.pytest_cache/`
- `data_cache/`
- `__pycache__/`

### Should not be touched until tests are stronger

- `intraday_momentum/reproduce.py`
- `Dockerfile`
- `docker-compose.yml`
- package import paths
- current baseline data paths

## 11. Staged Implementation Plan

### Stage 0: freeze baseline

Files changed:
- none or only docs if needed

Commands:
- `pytest`
- `docker compose up --build reproduce`

Acceptance criteria:
- both pass,
- outputs appear under `outputs/`.

Rollback risk:
- none

### Stage 1: planning docs

Files changed:
- `docs/repository_restructuring_plan.md`

Commands:
- optional docs build

Acceptance criteria:
- plan committed,
- no behavior changes.

Rollback risk:
- none

### Stage 2: data manifest and preprocessing skeleton

Files changed:
- add `preprocessing/`
- add schema and manifest scripts
- maybe expand `data/README.md`

Commands:
- `pytest`
- `python -m intraday_momentum.reproduce`
- `docker compose up --build reproduce`

Acceptance criteria:
- current baseline unchanged,
- new manifest generation deterministic.

Rollback risk:
- low if no current imports are touched

### Stage 3: careful organizational wrappers

Files changed:
- optional new `strategy_development/README.md`
- optional wrappers/config folders
- no package move yet

Commands:
- `pytest`
- `docker compose up --build reproduce`

Acceptance criteria:
- conceptual structure clearer,
- current package unchanged.

Rollback risk:
- low

### Stage 4: update reproduce pipeline documentation only, then code if needed

Files changed:
- README/docs first
- later controlled updates to reproduction orchestration

Acceptance criteria:
- canonical command remains unchanged.

Rollback risk:
- medium

### Stage 5: 15-minute cross-asset loader and deterministic splits

Files changed:
- preprocessing modules
- possibly `intraday_momentum.data`
- tests

Commands:
- `pytest`
- specific split-generation command
- `docker compose up --build reproduce`

Acceptance criteria:
- no live downloads,
- splits deterministic,
- baseline still works.

Rollback risk:
- medium

### Stage 6: strategy experiments on 15-minute assets

Files changed:
- experiment runner modules
- outputs/report generation

Acceptance criteria:
- 5-minute baseline still reproducible,
- 15-minute experiments runnable in deterministic mode.

Rollback risk:
- medium-high

### Stage 7: optimization

Files changed:
- optimization modules/configs
- validation-selection outputs

Acceptance criteria:
- train only for tuning,
- validation only for model selection,
- seeds fixed.

Rollback risk:
- high if leakage is introduced

### Stage 8: trade dependency layer

Files changed:
- `trade_dependency/`

Acceptance criteria:
- deterministic feature generation,
- outputs and figures stable.

Rollback risk:
- medium

### Stage 9: final portfolio layer

Files changed:
- `final_portfolio/`

Acceptance criteria:
- equal weight, Kelly-style, and Markowitz implemented deterministically,
- OOS only.

Rollback risk:
- high if train/validation/test boundaries are violated

### Stage 10: final documentation cleanup

Files changed:
- `README.md`
- docs
- data documentation

Acceptance criteria:
- repo story and actual pipeline match exactly.

Rollback risk:
- low

## 12. Critical Reproducibility Guardrails

These guardrails are mandatory after every future stage:

- `docker compose up --build reproduce` must pass after each stage.
- `pytest` must pass after each stage.
- no live downloads in the final reproduction path.
- no QuantConnect dependency.
- no Lean CLI dependency.
- no manual notebook execution.
- all data paths relative.
- all randomness seeded.
- all outputs stable and deterministic.
- every generated artifact documented.
- all final data committed or accompanied by deterministic checksums/manifests.

## Final Recommendation

The best path is not to replace `intraday_momentum/` with a prettier folder layout. The best path is:

1. keep the working package stable,
2. add the missing conceptual layers around it,
3. document roles clearly,
4. expand to 15-minute cross-asset research in a deterministic way,
5. only consider package relocation after the broader research pipeline and test suite are mature.

QuantConnect integration is explicitly skipped for now. The preserved original files remain valuable reference artifacts, but the final project should remain fully local, deterministic, and Docker-first.
