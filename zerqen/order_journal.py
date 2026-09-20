from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class JournalRecord:
    client_order_id: str
    status: str
    filled_quantity: float
    average_price: float

class OrderJournal:
    """Small deterministic recovery journal; production storage can replace it."""
    def __init__(self) -> None:
        self._records: dict[str, JournalRecord] = {}

    def append(self, record: JournalRecord) -> None:
        self._records[record.client_order_id] = record

    def recover(self, client_order_id: str) -> JournalRecord | None:
        return self._records.get(client_order_id)

    def pending(self, known_ids: set[str]) -> tuple[JournalRecord, ...]:
        return tuple(record for key, record in self._records.items() if key in known_ids)
