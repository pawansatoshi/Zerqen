from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class HealthStatus:
    healthy: bool
    checks: dict[str, bool]
    reasons: tuple[str, ...]

def system_health(*, data_available: bool, execution_available: bool, reconciliation_balanced: bool, drawdown: float, max_drawdown: float) -> HealthStatus:
    checks = {
        "data_available": data_available,
        "execution_available": execution_available,
        "reconciliation_balanced": reconciliation_balanced,
        "drawdown_within_limit": drawdown < max_drawdown,
    }
    reasons = tuple(name for name, passed in checks.items() if not passed)
    return HealthStatus(not reasons, checks, reasons)
