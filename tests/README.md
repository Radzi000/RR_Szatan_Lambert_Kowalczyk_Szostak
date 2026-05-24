# Tests

This folder contains minimal tests focused on reproducibility and pipeline stability.

The goal is not extensive unit testing, but ensuring that the core research workflow still works after refactors or cleanup.

## Main checks

### `test_preprocessing.py`
Verifies:
- preprocessing utilities work correctly,
- 15-minute datasets are detected,
- equities / commodities / crypto data exist,
- schema validation passes,
- manifests are generated correctly,
- global train/validation/test splits are deterministic.

### `test_reproduce.py`
Verifies:
- committed data files exist,
- the pipeline works fully offline,
- outputs are generated correctly,
- all 5 strategies are executed,
- the main reproduce command works:
  ```bash
  python -m strategy_development.local_implementation.reproduce