from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Iterable
from typing import Any

import pandas as pd

from .validation import chronological_split


@dataclass(frozen=True)
class OOSResult:
    params: dict[str, Any]
    train_score: float
    test_score: float


def select_on_train_only(
    frame: pd.DataFrame,
    parameter_grid: Iterable[dict[str, Any]],
    evaluator: Callable[[pd.DataFrame, dict[str, Any]], float],
    train_fraction: float = 0.7,
    maximize: bool = True,
) -> OOSResult:
    """Select parameters on train data, then evaluate the winner once on holdout."""
    split = chronological_split(frame, train_fraction)
    candidates = list(parameter_grid)
    if not candidates:
        raise ValueError("parameter_grid cannot be empty")

    scored = [(params, float(evaluator(split.train, params))) for params in candidates]
    best_params, train_score = max(scored, key=lambda item: item[1]) if maximize else min(
        scored, key=lambda item: item[1]
    )
    test_score = float(evaluator(split.test, best_params))
    return OOSResult(dict(best_params), train_score, test_score)
