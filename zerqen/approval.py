from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class LiveApproval:
    approved: bool
    operator: str
    reason: str

def approve_live(operator: str, reason: str) -> LiveApproval:
    if not operator.strip():
        raise ValueError("operator is required")
    if not reason.strip():
        raise ValueError("approval reason is required")
    return LiveApproval(True, operator.strip(), reason.strip())
