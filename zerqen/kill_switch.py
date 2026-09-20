from __future__ import annotations
from dataclasses import dataclass

@dataclass
class KillSwitch:
    tripped: bool = False
    reason: str = ""

    def trip(self, reason: str) -> None:
        if not reason:
            raise ValueError("kill switch reason is required")
        self.tripped = True
        self.reason = reason

    def reset(self) -> None:
        self.tripped = False
        self.reason = ""

    def allow_orders(self) -> bool:
        return not self.tripped
