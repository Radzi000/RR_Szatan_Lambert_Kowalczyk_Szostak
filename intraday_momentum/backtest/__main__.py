"""Compatibility entry point for legacy `python -m intraday_momentum.backtest` usage."""

from __future__ import annotations

from ..reproduce import main


if __name__ == "__main__":
    raise SystemExit(main())
