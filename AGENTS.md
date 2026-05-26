# AGENTS

## Project Goal

This repository is a reproducible research project for locally reproducing and
extending five QuantConnect-style intraday momentum strategies with committed
offline data and deterministic outputs.

Pipeline story:

- `data`
- `preprocessing`
- `strategy_development`
- `trade_dependency`
- `final_portfolio`
- `outputs`

## Canonical Commands

- Local tests: `pytest`
- Local reproduction: `python -m strategy_development.local_implementation.reproduce`
- Fixed 15-minute baseline: `python -m strategy_development.local_implementation.run_fixed_15m_experiments`
- Workstream C optimization: `python -m strategy_development.local_implementation.optimization.run_all_optimizations`
- Workstream C optimization smoke: `python -m strategy_development.local_implementation.optimization.run_all_optimizations --smoke`
- Docker reproduction: `docker compose up --build reproduce`
- Docker optimization smoke: `docker compose run --rm optimization`
- Clean Docker rebuild: `docker compose down`, `docker compose build --no-cache`, `docker compose up reproduce`

If you change code or docs that affect the pipeline, rerun the local commands.
If Docker is available, keep the Docker command passing too.

## Non-Negotiable Rules

- Do not reintroduce QuantConnect, Lean CLI, or any cloud dependency into the
  canonical reproduction path.
- Do not add live downloads to the final reproduction path.
- Keep all project paths relative.
- Keep the repository offline-reproducible from committed inputs.
- Preserve `strategy_development/taken_strategies/` as reference-only original
  strategy files.
- Treat `strategy_development/local_implementation/` as the authoritative local
  implementation.
- Do not change strategy behavior unless the task explicitly requires it.

## Optimization Guardrails

- Never use validation or test data during optimizer fitting.
- Use train only for parameter search.
- Use validation only for model/parameter selection.
- Use test only for final out-of-sample evaluation.
- If adding Workstream C functionality, ensure emitted outputs distinguish
  `train`, `validation`, and `test` explicitly.
- Never load the `test` partition inside optimization scripts.
- Keep Workstream C deterministic with explicit seeds.

## Data And Preprocessing Guardrails

- Prefer consuming deterministic preprocessing outputs under
  `data/processed/`.
- The A/B handoff for Workstream C is:
  `data/processed/manifests/data_manifest.json`,
  `data/processed/splits/global_time_splits.json`,
  `data/processed/unified/*.csv`,
  and `data/processed/splits/csv/*.csv`.
- Keep schema assumptions explicit and consistent with the shared OHLCV
  contract:
  `timestamp, open, high, low, close, volume`.
- Keep session assumptions explicit when mixing equities, commodities, and
  crypto.

## Output Conventions

- Write generated artifacts under `outputs/`.
- Tables go under `outputs/tables/`.
- Figures go under `outputs/figures/`.
- Reports go under `outputs/report/`.
- Favor stable filenames and deterministic content.
- When adding new pipeline stages, emit machine-readable tables before adding
  presentation-only summaries.
- The canonical Docker run should leave the expected outputs on the host in the
  bind-mounted `outputs/` directory and exit code `0`.
- The fixed 15-minute baseline runner should emit:
  `fixed_15m_strategy_summary.csv`,
  `fixed_15m_strategy_returns.csv`,
  `fixed_15m_trade_logs.csv`,
  and `fixed_15m_train_validation_test_summary.csv`.
- The Workstream C aggregate runner should emit:
  `optimization_search_results.csv`,
  `selected_params.csv`,
  `train_validation_comparison.csv`,
  `optimization_verification_metrics.csv`,
  `optimization_convergence.png`,
  and `train_validation_sharpe_comparison.png`.

## Documentation And Tests

- Update tests when changing behavior, interfaces, or output contracts.
- Update `README.md` and relevant docs when the implemented pipeline changes.
- Prefer documenting what is reproducible now versus what is planned later.
