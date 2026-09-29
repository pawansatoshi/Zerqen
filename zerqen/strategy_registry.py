from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


StrategyFn = Callable[..., pd.Series]


@dataclass(frozen=True)
class StrategySpec:
    name: str
    function: StrategyFn
    description: str


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, StrategySpec] = {}

    def register(self, name: str, function: StrategyFn, description: str = "") -> None:
        if not name or name in self._strategies:
            raise ValueError(f"Strategy name already registered: {name}")
        self._strategies[name] = StrategySpec(name, function, description)

    def get(self, name: str) -> StrategySpec:
        try:
            return self._strategies[name]
        except KeyError as exc:
            raise KeyError(f"Unknown strategy: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._strategies))

    def run(self, name: str, frame: pd.DataFrame, **kwargs) -> pd.Series:
        return self.get(name).function(frame, **kwargs)


def default_registry() -> StrategyRegistry:
    from .strategies import breakout_strategy, mean_reversion_strategy, trend_strategy

    registry = StrategyRegistry()
    registry.register("trend", trend_strategy, "EMA crossover with RSI confirmation")
    registry.register("mean_reversion", mean_reversion_strategy, "RSI recovery from an oversold condition")
    registry.register("breakout", breakout_strategy, "Prior-range breakout with volume confirmation")
    return registry


from enum import StrEnum


class StrategyStatus(StrEnum):
    VALIDATED = "VALIDATED"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class StrategyEvidence:
    strategy_id: str
    status: StrategyStatus = StrategyStatus.INSUFFICIENT_DATA
    regime_labels: tuple[str, ...] = ()
    score: float | None = None
    evidence_ref: str | None = None


DEFAULT_EVIDENCE = (
    StrategyEvidence("trend", StrategyStatus.INSUFFICIENT_DATA, ("trend_up", "trend_down", "breakout")),
    StrategyEvidence("momentum", StrategyStatus.INSUFFICIENT_DATA, ("trend_up", "trend_down")),
    StrategyEvidence("mean_reversion", StrategyStatus.INSUFFICIENT_DATA, ("range", "low_volatility")),
    StrategyEvidence("breakout", StrategyStatus.INSUFFICIENT_DATA, ("breakout", "high_volatility")),
)


def eligible_strategies(regime: str | None = None, evidence=DEFAULT_EVIDENCE) -> tuple[StrategyEvidence, ...]:
    return tuple(
        item for item in evidence
        if item.status == StrategyStatus.VALIDATED
        and (regime is None or regime in item.regime_labels)
    )
