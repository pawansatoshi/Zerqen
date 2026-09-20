from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

import pandas as pd


SignalFunction = Callable[[pd.DataFrame], pd.Series]


@dataclass(frozen=True)
class EnsembleConfig:
    threshold: float = 0.67
    trend_weight: float = 1.0
    mean_reversion_weight: float = 1.0
    breakout_weight: float = 1.0
    confirmation_weight: float = 1.0


def ensemble_score(
    frame: pd.DataFrame,
    signals: dict[str, pd.Series],
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    if not signals:
        raise ValueError("signals cannot be empty")
    index = frame.index
    aligned = {}
    for name, signal in signals.items():
        s = signal.reindex(index).fillna(False).astype(bool)
        aligned[name] = s.astype(float)

    weights = weights or {name: 1.0 for name in signals}
    missing = set(signals) - set(weights)
    if missing:
        raise ValueError(f"Missing weights for: {sorted(missing)}")

    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("total weight must be positive")

    score = sum(aligned[name] * weights[name] for name in aligned) / total_weight
    out = pd.DataFrame(aligned, index=index)
    out["score"] = score
    return out


def ensemble_entry(frame: pd.DataFrame, signals: dict[str, pd.Series],
                   threshold: float = 0.67,
                   weights: dict[str, float] | None = None) -> pd.Series:
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")
    return (ensemble_score(frame, signals, weights)["score"] >= threshold)
