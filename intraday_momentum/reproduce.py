"""Compatibility wrapper for legacy `python -m intraday_momentum.reproduce` usage."""

from __future__ import annotations

from strategy_development.local_implementation.reproduce import main, run_reproduction


if __name__ == "__main__":
    raise SystemExit(main())
