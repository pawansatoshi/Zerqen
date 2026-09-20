from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from typing import Any

@dataclass(frozen=True)
class AuditEvent:
    event: str
    timestamp: str
    run_id: str
    payload: dict[str, Any]

    @classmethod
    def create(cls, event: str, run_id: str, **payload: Any) -> "AuditEvent":
        return cls(event, datetime.now(timezone.utc).isoformat(), run_id, payload)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

class AuditLog:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: str, run_id: str, **payload: Any) -> AuditEvent:
        item = AuditEvent.create(event, run_id, **payload)
        self.events.append(item)
        return item

    def export_jsonl(self) -> str:
        return "\n".join(event.to_json() for event in self.events)
