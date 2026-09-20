from __future__ import annotations
from dataclasses import dataclass
from .adapters import AdapterResult, PaperExchangeAdapter
from .orders import Order, OrderStatus

@dataclass(frozen=True)
class DryRunResult:
    order: Order
    result: AdapterResult

class DryRunExecutor:
    """Always simulates orders and never permits a live adapter."""
    def __init__(self) -> None:
        self.adapter = PaperExchangeAdapter()

    def submit(self, order: Order, reference_price: float) -> DryRunResult:
        return DryRunResult(order, self.adapter.submit(order, reference_price))

    def is_live(self) -> bool:
        return False
