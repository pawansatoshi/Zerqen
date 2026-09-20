from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .validation import Split, rolling_walk_forward


@dataclass(frozen=True)
class WalkForwardResult:
    window: int
    train_score: float
    test_score: float
    parameters: dict[str, Any]


@dataclass(frozen=True)
class WalkForwardSummary:
    windows: tuple[WalkForwardResult, ...]
    mean_test_score: float
    median_test_score: float
    positive_test_fraction: float


def run_walk_forward(
    frame: pd.DataFrame,
    parameter_grid: Iterable[dict[str, Any]],
    evaluator: Callable[[pd.DataFrame, dict[str, Any]], float],
    train_size: int,
    test_size: int,
    step: int | None = None,
    maximize: bool = True,
) -> WalkForwardSummary:
    candidates = list(parameter_grid)
    if not candidates:
        raise ValueError("parameter_grid cannot be empty")
    splits: list[Split] = rolling_walk_forward(frame, train_size, test_size, step)
    if not splits:
        raise ValueError("frame is too small for requested walk-forward windows")

    results = []
    for index, split in enumerate(splits):
        scored = [
            (params, float(evaluator(split.train, params)))
            for params in candidates
        ]
        winner, train_score = (
            max(scored, key=lambda item: item[1])
            if maximize
            else min(scored, key=lambda item: item[1])
        )
        test_score = float(evaluator(split.test, winner))
        results.append(
            WalkForwardResult(index, train_score, test_score, dict(winner))
        )

    test_scores = pd.Series([item.test_score for item in results], dtype=float)
    return WalkForwardSummary(
        tuple(results),
        float(test_scores.mean()),
        float(test_scores.median()),
        float((test_scores > 0).mean()),
    )
