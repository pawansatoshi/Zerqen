from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class StrategyAllocation:
    name: str
    score: float
    weight: float
    capital: float


def allocate_by_score(
    equity: float,
    scores: dict[str, float],
    max_strategy_weight: float = 0.60,
    min_score: float = 0.0,
) -> tuple[StrategyAllocation, ...]:
    if equity <= 0:
        raise ValueError("equity must be positive")
    if not scores:
        return ()
    if not 0 < max_strategy_weight <= 1:
        raise ValueError("max_strategy_weight must be in (0, 1]")
    clean = {
        name: float(score)
        for name, score in scores.items()
        if isfinite(float(score)) and float(score) > min_score
    }
    if not clean:
        return ()
    total = sum(clean.values())
    raw = {name: value / total for name, value in clean.items()}
    capped = {name: min(weight, max_strategy_weight) for name, weight in raw.items()}
    used = sum(capped.values())
    if used <= 0:
        return ()
    normalized = {name: weight / used for name, weight in capped.items()}
    return tuple(
        StrategyAllocation(name, clean[name], normalized[name], equity * normalized[name])
        for name in sorted(normalized)
    )
