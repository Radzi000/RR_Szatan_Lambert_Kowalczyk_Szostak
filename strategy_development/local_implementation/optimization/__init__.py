"""Parameter optimization for intraday momentum strategies.

This module provides tools for tuning strategy hyperparameters using
evolutionary optimization algorithms (CMA-ES). It includes pre-defined
parameter spaces for each strategy variant and a unified
:class:`StrategyTuner` interface.
"""

from .param_spaces import PARAM_SPACES, ParamSpace
from .tuner import StrategyTuner

__all__ = ["StrategyTuner", "ParamSpace", "PARAM_SPACES"]
