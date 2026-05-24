"""Default parameter spaces for strategy tuning.

Each strategy variant has a :class:`ParamSpace` that defines which
parameters can be tuned, their bounds, and sensible starting points.
CMA-ES works in continuous space, so integer parameters are rounded
after sampling.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParamBound:
    """Single parameter specification.

    Attributes
    ----------
    name : str
        Parameter name matching the strategy constructor keyword.
    low : float
        Lower bound (inclusive).
    high : float
        Upper bound (inclusive).
    default : float
        Starting / centre value for CMA-ES.
    is_int : bool
        Whether the parameter should be rounded to an integer.
    """

    name: str
    low: float
    high: float
    default: float
    is_int: bool = False


@dataclass
class ParamSpace:
    """Collection of tunable parameters for a strategy.

    Attributes
    ----------
    strategy_class_name : str
        Fully-qualified or short name of the target strategy class.
    params : list[ParamBound]
        Tunable parameter definitions.
    """

    strategy_class_name: str
    params: list[ParamBound] = field(default_factory=list)

    @property
    def dimension(self) -> int:
        """Number of tunable parameters."""
        return len(self.params)

    @property
    def names(self) -> list[str]:
        """Ordered list of parameter names."""
        return [p.name for p in self.params]

    @property
    def defaults(self) -> list[float]:
        """Ordered list of default (starting) values."""
        return [p.default for p in self.params]

    @property
    def bounds_low(self) -> list[float]:
        """Ordered list of lower bounds."""
        return [p.low for p in self.params]

    @property
    def bounds_high(self) -> list[float]:
        """Ordered list of upper bounds."""
        return [p.high for p in self.params]

    def clip_and_round(self, raw_vector: list[float]) -> dict[str, float | int]:
        """Clip a raw CMA-ES sample to bounds and round integers.

        Parameters
        ----------
        raw_vector : list[float]
            Continuous values sampled by the optimizer (length == dimension).

        Returns
        -------
        dict[str, float | int]
            Parameter name → clipped (and optionally rounded) value.
        """
        result: dict[str, float | int] = {}
        for param, value in zip(self.params, raw_vector):
            clipped = max(param.low, min(param.high, value))
            result[param.name] = int(round(clipped)) if param.is_int else round(clipped, 6)
        return result


# ------------------------------------------------------------------
# Pre-defined spaces for each strategy variant
# ------------------------------------------------------------------

PARAM_SPACES: dict[str, ParamSpace] = {
    "Strategy0": ParamSpace(
        strategy_class_name="Strategy0",
        params=[
            ParamBound("lookback", 5, 30, 14, is_int=True),
            ParamBound("vol_target", 0.005, 0.05, 0.02),
            ParamBound("entry_interval", 10, 60, 30, is_int=True),
        ],
    ),
    "Strategy1": ParamSpace(
        strategy_class_name="Strategy1",
        params=[
            ParamBound("lookback", 5, 30, 14, is_int=True),
            ParamBound("vol_target", 0.005, 0.05, 0.02),
            ParamBound("entry_interval", 10, 60, 30, is_int=True),
            ParamBound("exit_interval", 1, 30, 5, is_int=True),
        ],
    ),
    "Strategy2": ParamSpace(
        strategy_class_name="Strategy2",
        params=[
            ParamBound("lookback", 5, 30, 14, is_int=True),
            ParamBound("vol_target", 0.005, 0.05, 0.02),
            ParamBound("entry_interval", 10, 60, 30, is_int=True),
            ParamBound("ema_period", 20, 200, 100, is_int=True),
        ],
    ),
    "Strategy3": ParamSpace(
        strategy_class_name="Strategy3",
        params=[
            ParamBound("lookback", 5, 30, 14, is_int=True),
            ParamBound("vol_target", 0.005, 0.05, 0.02),
            ParamBound("entry_interval", 10, 60, 30, is_int=True),
            ParamBound("exit_interval", 1, 30, 5, is_int=True),
            ParamBound("exit_confirmation_bars", 1, 10, 4, is_int=True),
        ],
    ),
    "Strategy4": ParamSpace(
        strategy_class_name="Strategy4",
        params=[
            ParamBound("lookback", 5, 30, 14, is_int=True),
            ParamBound("vol_target", 0.005, 0.05, 0.02),
            ParamBound("entry_interval", 10, 60, 30, is_int=True),
            ParamBound("exit_interval", 1, 30, 5, is_int=True),
            ParamBound("exit_confirmation_bars", 1, 10, 4, is_int=True),
            ParamBound("ema_period", 20, 200, 100, is_int=True),
        ],
    ),
}
