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
- future experiment configuration files,
- future fixed-parameter and tuned-parameter experiment metadata.
