from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True)
class CompoundingStep:
    day: int
    starting_equity: float
    realized_return: float
    ending_equity: float


def compound_path(
    starting_equity: float,
    daily_returns: Iterable[float],
) -> tuple[CompoundingStep, ...]:
    if starting_equity <= 0:
        raise ValueError("starting_equity must be positive")
    equity = float(starting_equity)
    steps = []
    for day, realized_return in enumerate(daily_returns, start=1):
        realized_return = float(realized_return)
        ending = max(0.0, equity * (1.0 + realized_return))
        steps.append(CompoundingStep(day, equity, realized_return, ending))
        equity = ending
    return tuple(steps)
