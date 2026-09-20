from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioRiskDecision:
    allowed: bool
    reason: str
    total_risk: float
    projected_drawdown: float


def portfolio_risk_check(
    equity: float,
    risk_amounts: list[float],
    *,
    max_total_risk: float = 0.015,
    current_drawdown: float = 0.0,
    max_drawdown: float = 0.20,
) -> PortfolioRiskDecision:
    if equity <= 0:
        return PortfolioRiskDecision(False, "non-positive equity", 0.0, current_drawdown)
    if any(risk < 0 for risk in risk_amounts):
        raise ValueError("risk amounts cannot be negative")
    if not 0 < max_total_risk <= 1:
        raise ValueError("max_total_risk must be in (0, 1]")
    if not 0 <= current_drawdown < 1:
        raise ValueError("current_drawdown must be in [0, 1)")
    total_risk = sum(risk_amounts) / equity
    projected = current_drawdown + total_risk
    if total_risk > max_total_risk:
        return PortfolioRiskDecision(False, "portfolio risk budget exceeded", total_risk, projected)
    if projected >= max_drawdown:
        return PortfolioRiskDecision(False, "projected drawdown limit exceeded", total_risk, projected)
    return PortfolioRiskDecision(True, "within portfolio risk budget", total_risk, projected)
