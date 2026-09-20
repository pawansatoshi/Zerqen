from __future__ import annotations
from dataclasses import dataclass
from .mode import TradingMode

@dataclass(frozen=True)
class PreflightResult:
    ready: bool
    checks: dict[str, bool]
    reasons: tuple[str, ...]

def run_preflight(
    mode: TradingMode,
    *,
    data_available: bool,
    credentials_present: bool,
    reconciliation_balanced: bool = True,
    risk_limits_valid: bool = True,
    explicit_live_enable: bool = False,
) -> PreflightResult:
    checks = {
        "data_available": data_available,
        "risk_limits_valid": risk_limits_valid,
        "reconciliation_balanced": reconciliation_balanced,
    }
    if mode in {TradingMode.TESTNET, TradingMode.LIVE}:
        checks["credentials_present"] = credentials_present
    if mode == TradingMode.LIVE:
        checks["explicit_live_enable"] = explicit_live_enable
    reasons = tuple(name for name, passed in checks.items() if not passed)
    return PreflightResult(not reasons, checks, reasons)
