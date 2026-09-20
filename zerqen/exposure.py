from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExposureDecision:
    allowed: bool
    reason: str
    requested: float
    accepted: float


def cap_exposure(
    equity: float,
    requested_notional: float,
    *,
    max_gross_leverage: float = 1.0,
) -> ExposureDecision:
    if equity <= 0:
        return ExposureDecision(False, "non-positive equity", requested_notional, 0.0)
    if requested_notional < 0:
        raise ValueError("requested_notional cannot be negative")
    if max_gross_leverage <= 0:
        raise ValueError("max_gross_leverage must be positive")
    cap = equity * max_gross_leverage
    accepted = min(requested_notional, cap)
    reason = "within exposure budget" if accepted == requested_notional else "exposure capped"
    return ExposureDecision(accepted > 0, reason, requested_notional, accepted)
