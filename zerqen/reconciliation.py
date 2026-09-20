from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ReconciliationResult:
    balanced: bool
    expected_quantity: float
    actual_quantity: float
    difference: float

def reconcile_position(expected_quantity: float, actual_quantity: float, *, tolerance: float = 1e-12) -> ReconciliationResult:
    if expected_quantity < 0 or actual_quantity < 0:
        raise ValueError("quantities cannot be negative")
    difference = actual_quantity - expected_quantity
    return ReconciliationResult(abs(difference) <= tolerance, expected_quantity, actual_quantity, difference)
