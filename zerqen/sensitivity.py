from dataclasses import dataclass
from itertools import product
from typing import Callable

@dataclass(frozen=True)
class SensitivityResult:
    parameters: dict
    score: float

def grid_search(
    parameter_grid: dict[str, list],
    evaluator: Callable[[dict], float],
) -> list[SensitivityResult]:
    names = list(parameter_grid)
    results = []
    for values in product(*(parameter_grid[name] for name in names)):
        params = dict(zip(names, values))
        results.append(SensitivityResult(params, float(evaluator(params))))
    return sorted(results, key=lambda item: item.score, reverse=True)
