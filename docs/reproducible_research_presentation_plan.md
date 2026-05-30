# Reproducible Research Presentation Plan

## Presentation Goal

Prepare a lecture presentation that explains this repository as a reproducible
research project, not only as a trading-strategy implementation. The central
message should be:

> A QuantConnect-style intraday momentum project was converted into an offline,
> deterministic, locally executable research pipeline with committed data,
> fixed commands, tests, Docker, stable outputs, and documented limitations.

The presentation should show what can be reproduced now, how the code supports
that claim, what results are generated, and what remains to be finished before
the project is a complete research artifact.

## Suggested Lecture Structure

### 1. Research Context

- Introduce the original upstream idea: five intraday momentum strategies.
- Explain the local research question:
  whether simple intraday momentum rules remain competitive after local
  reproduction and extension with timing, EMA filtering, confirmation, and
  combined variants.
- State the reproducibility challenge:
  the original strategy format depends on QuantConnect-style code, while this
  repository must run locally without cloud services or live downloads.

### 2. Reproducibility Design

Use the repository pipeline as the organizing diagram:

```text
data -> preprocessing -> strategy_development -> trade_dependency
     -> final_portfolio -> outputs
```

Important points:

- committed input data under `data/`,
- deterministic preprocessing under `preprocessing/`,
- reference-only original strategies under
  `strategy_development/taken_strategies/`,
- authoritative local implementation under
  `strategy_development/local_implementation/`,
- generated tables, figures, and reports under `outputs/`,
- tests under `tests/`,
- Docker workflow through `docker compose up --build reproduce`.

### 3. What Is Reproducible Now

Show the current reproducible baseline:

- command:
  `python -m strategy_development.local_implementation.reproduce`,
- Docker command:
  `docker compose up --build reproduce`,
- local test command:
  `pytest`,
- generated report:
  `outputs/report/final_report.md`,
- generated summary table:
  `outputs/tables/strategy_summary.csv`,
- generated figures:
  `outputs/figures/equity_curves.png` and
  `outputs/figures/drawdowns.png`.

Main result to mention from the current generated report:

- best baseline total return:
  `Strategy3 / Exit Confirmation`,
- all reported baseline metrics are net of transaction costs,
- no notebooks, live downloads, QuantConnect cloud, or Lean CLI are required.

### 4. Data And Preprocessing

Explain why data handling is central to reproducible research:

- raw committed files exist for SPY daily, SPY 5-minute, and broader 15-minute
  assets across equities, commodities, and crypto,
- preprocessing normalizes schema to:
  `timestamp, open, high, low, close, volume`,
- manifests include checksums,
- train/validation/test split boundaries are deterministic,
- downstream Workstream C inputs live under `data/processed/`.

Reproducibility angle:

- the data are not fetched live,
- paths are relative,
- split logic is chronological rather than random,
- mixed asset sessions are documented but still need stronger validation.

### 5. Strategy Translation

Explain the core code contribution:

- original QuantConnect-style files are preserved as reference artifacts,
- local Python strategies are implemented separately,
- the local backtest engine replaces QuantConnect runtime assumptions,
- transaction costs are centralized in
  `strategy_development/local_implementation/costs.py`,
- the five strategy variants are:
  `Strategy0 / Baseline`,
  `Strategy1 / Asymmetric Intervals`,
  `Strategy2 / EMA Filter`,
  `Strategy3 / Exit Confirmation`,
  `Strategy4 / EMA + Confirmation`.

Focus on reproducibility:

- preserving original files keeps provenance,
- local implementation makes execution inspectable,
- centralized costs reduce hidden assumptions,
- generated outputs make results auditable.

### 6. Extension Layer And Optimization

Present the 15-minute and Workstream C layer as the research extension:

- fixed 15-minute baseline command:
  `python -m strategy_development.local_implementation.run_fixed_15m_experiments`,
- optimization command:
  `python -m strategy_development.local_implementation.optimization.run_all_optimizations`,
- smoke optimization command:
  `python -m strategy_development.local_implementation.optimization.run_all_optimizations --smoke`,
- current Quarto report skeleton:
  `reports/workstream_c_optimization_report.qmd`.

Reproducibility constraints:

- optimizer fitting uses train only,
- validation is only for selection and verification,
- test is reserved for final out-of-sample evaluation,
- outputs explicitly separate train and validation,
- optimization metrics are net of transaction costs.

### 7. Results To Show

Prioritize visuals that support reproducibility and interpretation:

- baseline strategy summary table,
- baseline equity curves,
- baseline drawdowns,
- taken-strategy versus local-strategy verification metrics,
- fixed 15-minute train/validation/test summary,
- optimization search convergence,
- train versus validation Sharpe comparison,
- our-strategy equity curves and drawdowns split by train and validation.

Avoid presenting only final returns. The lecture should show the full chain:
input data, command, generated artifacts, result, and limitation.

### 8. Limitations And Remaining Work

Be explicit about what still needs to be done:

- build a Quarto presentation file, likely
  `reports/reproducible_research_presentation.qmd`,
- render it to HTML or slides and verify all images/tables load from relative
  paths,
- add a clean pipeline diagram and result flow diagram,
- improve visualizations for lecture use:
  clearer equity/drawdown charts, data coverage plots, train/validation/test
  timeline, asset-class coverage, cost impact, and optimization diagnostics,
- add a concise code walkthrough section so presenters understand the actual
  modules and not just the README,
- decide which outputs are canonical for the lecture and regenerate them before
  presenting,
- verify Docker on a working machine,
- tighten mixed-session and missing-bar validation,
- remove or clearly mark stale documentation references,
- complete final out-of-sample test evaluation only after model selection is
  frozen,
- develop `trade_dependency/` and `final_portfolio/` or clearly label them as
  future work.

## Proposed Slide Outline

1. Title and team
2. Research question and upstream project
3. What reproducibility means in this project
4. Repository pipeline diagram
5. Data sources and committed-data policy
6. Deterministic preprocessing and checksums
7. Train/validation/test split discipline
8. Original versus local strategy implementation
9. Backtest engine and centralized transaction costs
10. One-command reproduction
11. Generated outputs and manifest
12. Baseline results
13. Equity curves and drawdowns
14. 15-minute cross-asset extension
15. Workstream C optimization discipline
16. Optimization outputs and diagnostics
17. Tests, Docker, and failure modes
18. Limitations
19. What still needs to be done
20. Final reproducibility checklist

## Four-Person Division

### Person 1: Radoslaw Szostak - Reproducibility Architecture

Main responsibility:

- explain the repository structure, canonical commands, Docker workflow, tests,
  and output contract.

Deliverables:

- slides for the pipeline diagram, reproducibility checklist, Docker/test
  workflow, and generated artifact map,
- live or recorded command demonstration:
  `pytest` and
  `python -m strategy_development.local_implementation.reproduce`,
- short explanation of `README.md`, `Makefile`, `Dockerfile`,
  `docker-compose.yml`, and `outputs/tables/reproducibility_manifest.json`.

Code knowledge needed:

- `strategy_development/local_implementation/reproduce.py`,
- `tests/test_reproduce.py`,
- `docker-compose.yml`,
- `Makefile`.

### Person 2: Eryk Szatan - Data And Preprocessing

Main responsibility:

- explain how committed data, schema normalization, manifests, and deterministic
  splits make the project reproducible.

Deliverables:

- slides for data layout, raw-to-processed flow, schema contract, checksums,
  and train/validation/test split logic,
- visualization of data coverage by asset class and time,
- train/validation/test timeline chart for the 15-minute extension.

Code knowledge needed:

- `data/README.md`,
- `preprocessing/validate_schema.py`,
- `preprocessing/build_data_manifest.py`,
- `preprocessing/make_global_splits.py`,
- `preprocessing/materialize_processed_data.py`,
- `tests/test_preprocessing.py`.

### Person 3: Kacper Lambert - Strategies And Backtesting

Main responsibility:

- explain how the original QuantConnect-style strategies were translated into
  local reproducible Python code.

Deliverables:

- slides comparing reference strategies with local implementation,
- table of five strategy variants and their assumptions,
- explanation of the local backtest loop and transaction-cost handling,
- improved baseline result visualizations for equity curves, drawdowns, and
  verification metrics.

Code knowledge needed:

- `strategy_development/taken_strategies/`,
- `strategy_development/local_implementation/strategies/`,
- `strategy_development/local_implementation/backtest/engine.py`,
- `strategy_development/local_implementation/costs.py`,
- `strategy_development/local_implementation/visualization/plots.py`.

### Person 4: Natalia Kowalczyk - Results, Optimization, And Presentation Build

Main responsibility:

- turn the outputs into a coherent Quarto slide deck and explain the extension
  and optimization layer.

Deliverables:

- create `reports/reproducible_research_presentation.qmd`,
- include generated figures and selected tables with relative paths,
- render the deck and check that it works from a clean clone,
- slides for fixed 15-minute baseline, Workstream C optimization discipline,
  train/validation comparison, and remaining work.

Code knowledge needed:

- `reports/workstream_c_optimization_report.qmd`,
- `strategy_development/local_implementation/run_fixed_15m_experiments.py`,
- `strategy_development/local_implementation/optimization/run_all_optimizations.py`,
- `strategy_development/local_implementation/optimization/tuner.py`,
- `outputs/tables/optimization_search_results.csv`,
- `outputs/tables/train_validation_comparison.csv`,
- `outputs/figures/optimization_convergence.png`,
- `outputs/figures/train_validation_sharpe_comparison.png`.

## Quarto Presentation To Build

Recommended file:

```text
reports/reproducible_research_presentation.qmd
```

Recommended format:

```yaml
---
title: "Reproducible Intraday Momentum Research"
subtitle: "Offline reproduction, deterministic outputs, and local extensions"
author:
  - Eryk Szatan
  - Kacper Lambert
  - Natalia Kowalczyk
  - Radoslaw Szostak
format:
  revealjs:
    toc: false
    slide-number: true
    chalkboard: false
execute:
  echo: false
---
```

The deck should not recompute expensive results during rendering. It should
read stable generated artifacts from `outputs/` and explain how to regenerate
them with the canonical commands.

## Visualization Checklist

Need for the lecture:

- repository pipeline diagram,
- data coverage by asset and asset class,
- train/validation/test split timeline,
- baseline strategy summary table,
- baseline equity curves,
- baseline drawdowns,
- local versus taken-strategy comparison,
- cost-aware metric comparison,
- optimization convergence plot,
- train versus validation Sharpe comparison,
- final reproducibility checklist.

Already available:

- `outputs/figures/equity_curves.png`,
- `outputs/figures/drawdowns.png`,
- `outputs/figures/equity_curves_taken_strats.png`,
- `outputs/figures/drawdowns_taken_strats.png`,
- `outputs/figures/equity_curves_our_strats.png`,
- `outputs/figures/drawdowns_our_strats.png`,
- `outputs/figures/optimization_convergence.png`,
- `outputs/figures/train_validation_sharpe_comparison.png`.

Still useful to add:

- data coverage heatmap or bar chart,
- train/validation/test split timeline,
- pipeline architecture diagram,
- one-slide artifact dependency graph,
- transaction-cost impact chart,
- final OOS/test evaluation chart after selection is frozen.

## Final Week Checklist

- Regenerate outputs with:
  `python -m strategy_development.local_implementation.reproduce`.
- Run:
  `python -m strategy_development.local_implementation.run_fixed_15m_experiments`.
- Run smoke optimization:
  `python -m strategy_development.local_implementation.optimization.run_all_optimizations --smoke`.
- Run:
  `pytest`.
- Render the Quarto deck.
- Verify all slide links are relative.
- Confirm every presenter can explain their assigned code files.
- Confirm the limitations slide says what is reproducible now versus planned.
- If Docker is available, run:
  `docker compose up --build reproduce`.
