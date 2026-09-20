from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RobustnessGate:
    passed: bool
    reasons: tuple[str, ...]


def evaluate_gate(
    *,
    positive_test_fraction: float,
    min_positive_test_fraction: float = 0.55,
    median_test_score: float = 0.0,
    min_median_test_score: float = 0.0,
    mc_terminal_p05: float | None = None,
    mc_max_drawdown_p95: float | None = None,
    max_allowed_drawdown: float = 0.20,
) -> RobustnessGate:
    reasons: list[str] = []
    if positive_test_fraction < min_positive_test_fraction:
        reasons.append("insufficient positive walk-forward windows")
    if median_test_score < min_median_test_score:
        reasons.append("median out-of-sample score below gate")
    if mc_terminal_p05 is not None and mc_terminal_p05 < 0:
        reasons.append("Monte Carlo 5th-percentile terminal return is negative")
    if mc_max_drawdown_p95 is not None and abs(mc_max_drawdown_p95) > max_allowed_drawdown:
        reasons.append("Monte Carlo 95th-percentile drawdown exceeds risk limit")
    return RobustnessGate(not reasons, tuple(reasons))
