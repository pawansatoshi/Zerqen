from __future__ import annotations
from dataclasses import dataclass
from .reconciliation import reconcile_position

@dataclass(frozen=True)
class LiveReconciliation:
    balanced: bool
    quantity_difference: float
    reason: str

def reconcile_live(expected_quantity: float, actual_quantity: float, tolerance: float = 1e-12) -> LiveReconciliation:
    result = reconcile_position(expected_quantity, actual_quantity, tolerance=tolerance)
    return LiveReconciliation(
        result.balanced,
        result.difference,
        "balanced" if result.balanced else "position drift detected",
    )
