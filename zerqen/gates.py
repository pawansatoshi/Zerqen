from __future__ import annotations
from dataclasses import dataclass
from .mode import TradingMode
from .preflight import PreflightResult

@dataclass(frozen=True)
class PromotionGate:
    allowed: bool
    reason: str

def promotion_gate(mode: TradingMode, preflight: PreflightResult, *, approved: bool = False) -> PromotionGate:
    if not preflight.ready:
        return PromotionGate(False, "preflight failed")
    if mode == TradingMode.LIVE and not approved:
        return PromotionGate(False, "live mode requires explicit approval")
    return PromotionGate(True, "mode permitted")
