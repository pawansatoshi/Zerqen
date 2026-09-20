from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(StrEnum):
    NEW = "new"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"

@dataclass(frozen=True)
class Order:
    client_order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: str = "market"

@dataclass(frozen=True)
class OrderEvent:
    client_order_id: str
    status: OrderStatus
    filled_quantity: float
    average_price: float
    message: str = ""

class OrderStateMachine:
    _allowed = {
        OrderStatus.NEW: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.CANCELED},
        OrderStatus.SUBMITTED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELED},
        OrderStatus.PARTIALLY_FILLED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED},
        OrderStatus.FILLED: set(), OrderStatus.CANCELED: set(), OrderStatus.REJECTED: set(),
    }

    def __init__(self) -> None:
        self._status: dict[str, OrderStatus] = {}

    def register(self, order: Order) -> None:
        if order.client_order_id in self._status:
            raise ValueError("client_order_id already registered")
        if order.quantity <= 0:
            raise ValueError("quantity must be positive")
        self._status[order.client_order_id] = OrderStatus.NEW

    def transition(self, client_order_id: str, status: OrderStatus) -> OrderStatus:
        current = self._status.get(client_order_id)
        if current is None:
            raise KeyError("unknown client_order_id")
        if status not in self._allowed[current]:
            raise ValueError(f"invalid transition: {current} -> {status}")
        self._status[client_order_id] = status
        return status

    def status(self, client_order_id: str) -> OrderStatus:
        return self._status[client_order_id]
