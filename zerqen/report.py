from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from typing import Any

@dataclass(frozen=True)
class RunReport:
    run_id: str
    mode: str
    metrics: dict[str, Any]
    risk: dict[str, Any]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

def build_run_report(run_id: str, mode: str, metrics: dict[str, Any], risk: dict[str, Any], status: str = "completed") -> RunReport:
    return RunReport(run_id, mode, metrics, risk, status)
