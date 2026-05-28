# Strategy Development

This directory contains the strategy-related parts of the repository.

## Current Role

- `taken_strategies/`
  Stores the original downloaded QuantConnect-style strategy files preserved as
  reference-only artifacts.
- `local_implementation/`
  Contains the authoritative local Python implementation used by Docker, tests,
  and the reproducible pipeline.

## Important Distinction

The authoritative local implementation now lives in
[strategy_development/local_implementation](/C:/Users/Rados/RR/strategy_development/local_implementation)
and is used by:

- `python -m strategy_development.local_implementation.reproduce`
- `pytest`
- `docker compose up --build reproduce`

This repository does **not** require:

- QuantConnect cloud,
- Lean CLI,
- QuantConnect APIs,
- a QuantConnect account.

The original QuantConnect-style files are preserved for interpretation and
comparison only.

## Planned Future Role

This directory is the research-facing home for:

- preserved upstream reference files,
- the current local executable implementation,
- fixed-parameter baseline experiment outputs,
- train/validation optimization entry points and outputs.

## Workstream C

Workstream C is implemented under
`strategy_development/local_implementation/optimization/`.

Canonical commands:

- `python -m strategy_development.local_implementation.optimization.run_strategy1_nes`
- `python -m strategy_development.local_implementation.optimization.run_strategy2_nes`
- `python -m strategy_development.local_implementation.optimization.run_strategy3_nes`
- `python -m strategy_development.local_implementation.optimization.run_strategy4_cmaes`
- `python -m strategy_development.local_implementation.optimization.run_strategy5_cmaes`
- `python -m strategy_development.local_implementation.optimization.run_all_optimizations`

Rules:

- strategies 1-3 use NES
- strategies 4-5 use CMA-ES
- optimization uses train only
- validation is used only for verification and parameter selection
- test/OOS remains reserved for a later final evaluation stage
- optimization and baseline verification are net of centralized transaction
  costs

Aggregate outputs are written under `outputs/tables/` and `outputs/figures/`.
