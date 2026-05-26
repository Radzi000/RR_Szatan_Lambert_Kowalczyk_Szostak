# Workstream C Readiness Audit

## Scope

This audit checks whether Workstream A (`preprocessing/` + `data/`) and
Workstream B (`strategy_development/`) are complete enough to safely start
Workstream C (`strategy_development/optimization/` + `trade_dependency/`)
without implementing C itself.

Audit date: 2026-05-26

## Baseline Verification

Verified locally before audit:

- `pytest`: passes
- `python -m strategy_development.local_implementation.reproduce`: passes

Environment-blocked:

- `docker compose up --build reproduce`: could not be executed end-to-end on
  this machine because the Docker Desktop Linux engine pipe was unavailable.
  `docker compose config` does resolve successfully, so the compose file itself
  is syntactically valid.

## 1. Repository Status

### Top-level structure

Current top-level structure:

- `data/`
- `docs/`
- `final_portfolio/`
- `outputs/`
- `preprocessing/`
- `strategy_development/`
- `tests/`
- `trade_dependency/`
- root infra: `README.md`, `Dockerfile`, `docker-compose.yml`, `Makefile`,
  `pyproject.toml`, `AI_USAGE.md`

### Cleanliness and stale references

The repository is mostly clean and minimal at the top level, but not fully
clean semantically:

- The local executable path is now `strategy_development/local_implementation/`.
- There is no top-level `intraday_momentum/` package anymore.
- Older docs and some docstrings still reference `intraday_momentum/` as the
  active package.
- `strategy_development/local_implementation/strategy_module.py` is a stale,
  duplicate strategy/backtest implementation that is not used by the canonical
  reproduce pipeline.
- `data/processed/unified/` and `data/processed/splits/csv/` exist only as
  placeholders in the committed tree; their generators exist, but the outputs
  are not materialized in-repo.

### Verdict

- Top-level structure: acceptable
- Cleanup completeness: partial
- Duplicate/stale logic still present: yes
- Broken conceptual references still present: yes
- `intraday_momentum/` wrapper status: not applicable, because the directory is
  no longer present; only stale references remain

## 2. A / Preprocessing Readiness

### What exists

Implemented preprocessing pieces:

- deterministic raw asset discovery
- schema normalization to a shared OHLCV contract
- SHA256 manifest generation
- documented asset metadata
- deterministic global 70/15/15 split boundary generation
- helper code for exporting unified CSVs
- helper code for exporting split CSVs
- smoke tests covering discovery, schema validation, determinism, and
  chronological non-overlap

### Question-by-question assessment

- Are all 15min assets discoverable: yes
- Are equities, commodities, and crypto all represented: yes
- Is there a common schema: yes
- Are OHLCV columns normalized: yes
- Are asset metadata fields available: yes
- Are SHA256/data manifests generated: yes
- Are global 70/15/15 time split boundaries generated: yes
- Is the split time-based, not random: yes
- Is the split deterministic across repeated runs: yes
- Is there any look-ahead or leakage risk: low in the current split logic, but
  not fully closed out operationally
- Are crypto/equity session differences documented: yes
- Are missing bars/timezones handled or at least explicitly documented: only
  partially
- Are data paths relative: yes
- Are live downloads disabled in final reproduction: yes

### Strengths

- `preprocessing/validate_schema.py` normalizes raw column variants into the
  shared `timestamp/open/high/low/close/volume` schema.
- `preprocessing/build_data_manifest.py` attaches deterministic metadata
  including `asset`, `asset_class`, `frequency`, `source_file`, `sha256`, and a
  session profile.
- `preprocessing/make_global_splits.py` creates deterministic chronological
  train/validation/test boundaries.
- `tests/test_preprocessing.py` checks asset discovery, manifest generation,
  split determinism, and non-overlap.

### Gaps relevant to C

1. The committed repo does not yet contain generated split CSVs under
   `data/processed/splits/csv/`, even though `preprocessing/loader.py` assumes
   those files exist for downstream consumption.
2. The global split boundaries are created from a synthetic dense
   `pd.date_range(..., freq="15min")` across the overlapping window, not from
   observed timestamps. This is deterministic and chronological, but it ignores
   real session gaps and mixed session structures across asset classes.
3. Missing-bar quality checks are not implemented. The current preprocessing
   layer documents session conventions, but it does not assert bar completeness,
   expected session counts, or calendar consistency.
4. Timezone normalization is present, but mixed-session handling is still a
   documentation-level contract rather than an enforced preprocessing contract.

### Strict A Verdict

`PARTIALLY READY`

Reason:

Workstream A is strong enough to define the data contract and prevent obvious
random-split leakage, but it is not fully finished as a production-ready input
layer for optimization because downstream split artifacts are not yet
materialized and session/missing-bar handling is still under-specified.

## 3. B / Strategy Rewrite Readiness

### What exists

Implemented strategy-development pieces:

- five preserved original QuantConnect-style strategy files under
  `strategy_development/taken_strategies/`
- five local Python strategy implementations under
  `strategy_development/local_implementation/strategies/`
- a local backtest engine independent of QuantConnect
- a deterministic local reproduce pipeline
- aggregate summary/report outputs for the 5-minute SPY baseline
- initial optimization scaffolding (`optimization/param_spaces.py`,
  `optimization/tuner.py`)

### Question-by-question assessment

- Are there exactly 5 local strategy implementations: yes
- Can each strategy run locally without QuantConnect: yes
- Are original downloaded QuantConnect-style strategies preserved as
  reference-only: yes
- Is the local backtester independent of QuantConnect: yes
- Does the fixed baseline run through the local reproduce pipeline: yes
- Is 15min cross-asset backtesting already implemented, or only 5m SPY
  baseline: only 5m SPY baseline
- Are parameter configs explicit and accessible: yes, for the 5 baseline runs,
  and partially for tuning scaffolding
- Are original/adapted parameters documented: partially
- Does the pipeline produce per-strategy outputs: only aggregate per-strategy
  summary outputs
- Does it produce per-asset outputs: no
- Does it produce trade logs, strategy returns, or only aggregate summary: only
  aggregate summary is persisted
- Are outputs sufficient as input for optimization and trade dependency: no
- Does the backtester expose returns/trades needed for C: in memory yes, in
  persisted artifacts no

### Strengths

- The authoritative local pipeline is deterministic and local-only.
- `BacktestResult` already exposes `equity_curve`, `trades`, and `signals`,
  which is a usable in-memory interface for future C work.
- `reproduce.py` clearly defines fixed baseline parameter sets for all five
  strategies.
- Tests verify the local reproduce path and stable output filenames.

### Gaps relevant to C

1. The canonical reproduce pipeline only loads bundled SPY daily + SPY 5-minute
   data and does not run the 15-minute multi-asset extension layer.
2. No committed or generated per-asset result tables exist for cross-asset
   optimization input.
3. No persisted trade log files or returns series are emitted under `outputs/`.
4. The existing CMA-ES scaffolding is not wired to train/validation/test splits
   and is therefore not yet safe as Workstream C infrastructure.
5. `strategy_development/local_implementation/strategy_module.py` is stale
   duplicate logic and risks confusing future contributors about what is
   canonical.

### Strict B Verdict

`PARTIALLY READY`

Reason:

Workstream B is complete enough for the reproducible 5-minute SPY baseline, but
not complete enough as the optimization substrate for C because the multi-asset
15-minute execution layer and persisted downstream artifacts do not exist yet.

## 4. Is C Allowed To Start?

### Short answer

Not as full NES/CMA-ES implementation against the intended extension layer.

### Can we start NES/CMAES now

- Full answer: no
- Infrastructure-only answer: yes

### Why not yet

The repository does not yet provide the main thing C needs:

- a canonical 15-minute cross-asset local backtest runner that consumes the
  preprocessing split contract and persists train/validation outputs per
  strategy and per asset

Without that layer, any optimizer would either:

- tune only the current 5m SPY baseline, which is not the intended C scope, or
- bypass the current A/B contract and create a second ad hoc pipeline

### Minimal blockers before full C

1. Materialize and standardize downstream split inputs:
   either committed generated split CSVs or a canonical generation step used by
   C.
2. Implement the 15-minute cross-asset local execution pipeline for the five
   adapted strategy variants.
3. Persist per-asset, per-strategy artifacts needed by C:
   returns, trades, and evaluation summaries.
4. Freeze the rule that optimization sees train only, model selection sees
   validation only, and test remains untouched.

### Should C start with infrastructure only

Yes.

The safe interpretation is:

- do not start optimizer research yet
- do start the interfaces, file contracts, and split-aware runner plumbing that
  C will need

### First safe C task

Build a split-aware experiment runner that:

- loads normalized/split 15-minute data from preprocessing outputs
- runs the existing five local strategies on `train`, `validation`, and `test`
  partitions separately
- persists per-strategy/per-asset summary tables and trade logs
- does not perform any parameter search yet

## 5. Required Interface For C

### C should consume

- normalized unified data or pre-split data from `preprocessing/`
- the global split manifest from `data/processed/splits/global_time_splits.json`
- explicit strategy definitions and parameter configs from
  `strategy_development/local_implementation/`
- train split only for optimization
- validation split only for model selection
- fixed baseline outputs if available

### C should never do

- use validation or test data during optimizer fitting
- emit test/OOS results during routine tuning runs
- depend on live downloads or QuantConnect

### Recommended input contract

- `data/processed/manifests/data_manifest.json`
- `data/processed/splits/global_time_splits.json`
- `data/processed/unified/{asset}_{asset_class}_{frequency}.csv`
- `data/processed/splits/csv/{asset}_{asset_class}_{frequency}_{partition}.csv`
- strategy module imports from
  `strategy_development.local_implementation.strategies`
- fixed baseline parameter definitions from
  `strategy_development/local_implementation/reproduce.py`

### Recommended output contract

- `outputs/tables/optimization_search_results.csv`
- `outputs/tables/selected_params.csv`
- `outputs/tables/train_validation_comparison.csv`
- `outputs/tables/trade_dependency_summary.csv`
- `outputs/tables/per_asset_strategy_summary.csv`
- `outputs/tables/per_trade_log.csv`
- `outputs/tables/per_bar_returns.csv`
- `outputs/figures/optimization_convergence.png`
- `outputs/figures/regime_performance.png`
- `outputs/figures/seasonality_performance.png`
- `outputs/figures/time_of_day_performance.png`

### Minimum schema suggestions

`outputs/tables/optimization_search_results.csv`

- strategy
- asset
- asset_class
- split_used_for_fit
- objective
- generation
- candidate_id
- params_json
- score_train
- seed

`outputs/tables/selected_params.csv`

- strategy
- asset
- asset_class
- selection_rule
- params_json
- train_score
- validation_score

`outputs/tables/train_validation_comparison.csv`

- strategy
- asset
- asset_class
- params_source
- total_return_train
- sharpe_train
- max_drawdown_train
- total_return_validation
- sharpe_validation
- max_drawdown_validation
- num_trades_train
- num_trades_validation

`outputs/tables/trade_dependency_summary.csv`

- strategy
- asset
- asset_class
- analysis_type
- bucket
- trade_count
- mean_return_pct
- win_rate
- sharpe_proxy

`outputs/tables/per_trade_log.csv`

- strategy
- asset
- asset_class
- split
- entry_time
- exit_time
- direction
- entry_price
- exit_price
- leverage
- pnl
- return_pct

`outputs/tables/per_bar_returns.csv`

- strategy
- asset
- asset_class
- split
- timestamp
- equity
- return_pct
- drawdown_pct

## 6. AGENTS.md Recommendation

An `AGENTS.md` file should exist at repo root and encode the project guardrails
for future agent work.

Recommended contents:

- project goal and pipeline scope
- canonical reproduction command
- canonical test command
- Docker command
- no QuantConnect dependency
- no live downloads in the final path
- no test-set usage during optimization
- keep paths relative
- keep Docker passing
- preserve original strategies in `strategy_development/taken_strategies/`
- treat `strategy_development/local_implementation/` as authoritative
- persist outputs under `outputs/`
- update tests and README when changing behavior

## 7. Pipeline Completeness

### Checked documentation

- `README.md`
- `docs/repository_restructuring_plan.md`
- `docs/strategy_data_audit.md`
- `data/README.md`
- `strategy_development/README.md`

### Assessment

- Is the full project pipeline clearly described somewhere: partially
- Does README explain
  `data -> preprocessing -> strategy_development -> trade_dependency -> final_portfolio -> outputs`:
  yes
- Does it distinguish current implemented baseline from planned future stages:
  yes, partially
- Are A, B, C, D responsibilities clear: mostly, but not in one authoritative
  execution contract
- Does it explain what is reproducible now vs planned: yes, but some older docs
  conflict with the current package layout

### Documentation gaps

1. `README.md` is the best current high-level description, but it still centers
   the reproducible baseline on 5m SPY.
2. `docs/repository_restructuring_plan.md` is explicitly historical, but it
   still contains many obsolete references to `intraday_momentum/`.
3. `docs/strategy_data_audit.md` is useful context, but it also includes stale
   `intraday_momentum/` references.
4. There is no single authoritative document yet for the exact A/B/C handoff
   contract.

## 8. Minimal Blocker List

### P0 = must fix before full C implementation

1. Add a canonical 15-minute cross-asset local execution path for the five
   local strategies.
2. Persist per-asset/per-strategy outputs needed by optimization and trade
   dependency:
   returns series, trade logs, and summary tables.
3. Wire downstream execution to the preprocessing split contract so train,
   validation, and test are handled explicitly and separately.
4. Remove ambiguity about canonical code by documenting
   `strategy_development/local_implementation/strategy_module.py` as stale or
   excluding it from future work.

### P1 = should fix during early C

1. Materialize `data/processed/unified/` and `data/processed/splits/csv/` via a
   canonical workflow and document whether they should be committed or generated.
2. Tighten session and missing-bar validation for mixed equities/commodities vs
   crypto inputs.
3. Clean stale `intraday_momentum/` references from docs and docstrings that now
   conflict with the actual package layout.
4. Decide and document the exact 15-minute parameter reinterpretation rules for
   Strategies 1-4.

### P2 = nice to have

1. Expand tests from smoke checks into split-aware multi-asset execution tests.
2. Emit richer diagnostics such as regime tags and bar-level metadata.
3. Add a dedicated README in `trade_dependency/` describing expected input file
   schemas once C starts landing.

## 9. Final Verdict

- A readiness: `PARTIALLY READY`
- B readiness: `PARTIALLY READY`
- Can full Workstream C begin: `NO`
- Can Workstream C infrastructure begin: `YES`

## 10. Suggested Next Prompt

Because readiness is not yet sufficient for full C, the next safe prompt should
be a blocker-removal prompt:

> Implement the minimum A/B handoff needed for Workstream C without doing
> optimization yet. Add a canonical 15-minute cross-asset local experiment
> runner that consumes `data/processed/splits/global_time_splits.json` and/or
> `data/processed/splits/csv/`, runs the five existing local strategies across
> all 15-minute assets, and writes per-asset/per-strategy summary tables, trade
> logs, and returns series under `outputs/tables/`. Do not use the test split
> for tuning, do not change strategy behavior, keep `pytest` and
> `python -m strategy_development.local_implementation.reproduce` passing, and
> keep Docker wiring unchanged.
