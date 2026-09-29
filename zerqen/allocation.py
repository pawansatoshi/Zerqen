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
    remaining = set(clean)
    normalized: dict[str, float] = {}
    remaining_weight = 1.0
    while remaining:
        total = sum(clean[name] for name in remaining)
        proposed = {name: remaining_weight * clean[name] / total for name in remaining}
        capped_now = {name for name, weight in proposed.items() if weight > max_strategy_weight}
        if not capped_now:
            normalized.update(proposed)
            break
        for name in capped_now:
            normalized[name] = max_strategy_weight
            remaining.remove(name)
            remaining_weight -= max_strategy_weight
        if remaining_weight < -1e-12:
            raise ValueError("max_strategy_weight cannot satisfy allocation")
    return tuple(
        StrategyAllocation(name, clean[name], normalized[name], equity * normalized[name])
        for name in sorted(normalized)
    )
