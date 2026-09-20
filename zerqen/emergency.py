from __future__ import annotations
from dataclasses import dataclass
from .kill_switch import KillSwitch

@dataclass(frozen=True)
class EmergencyAction:
    action: str
    reason: str

def emergency_stop(kill_switch: KillSwitch, reason: str) -> EmergencyAction:
    kill_switch.trip(reason)
    return EmergencyAction("halt_new_orders", reason)
