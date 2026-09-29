from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar
from enum import StrEnum


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    CREATED = "created"
    RISK_CHECK = "risk_check"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    FAILED = "failed"
    UNKNOWN = "unknown"


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
    _allowed: ClassVar[dict[OrderStatus, set[OrderStatus]]] = {
        OrderStatus.CREATED: {OrderStatus.RISK_CHECK, OrderStatus.REJECTED, OrderStatus.FAILED},
        OrderStatus.RISK_CHECK: {OrderStatus.APPROVED, OrderStatus.REJECTED},
        OrderStatus.APPROVED: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.FAILED},
        OrderStatus.SUBMITTED: {OrderStatus.ACKNOWLEDGED, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED,
                                OrderStatus.CANCEL_REQUESTED, OrderStatus.CANCELED, OrderStatus.REJECTED,
                                OrderStatus.EXPIRED, OrderStatus.FAILED, OrderStatus.UNKNOWN},
        OrderStatus.ACKNOWLEDGED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED,
                                   OrderStatus.CANCEL_REQUESTED, OrderStatus.CANCELED,
                                   OrderStatus.EXPIRED, OrderStatus.FAILED, OrderStatus.UNKNOWN},
        OrderStatus.PARTIALLY_FILLED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED,
                                       OrderStatus.CANCEL_REQUESTED, OrderStatus.CANCELED,
                                       OrderStatus.EXPIRED, OrderStatus.UNKNOWN},
        OrderStatus.CANCEL_REQUESTED: {OrderStatus.CANCELED, OrderStatus.FILLED,
                                       OrderStatus.PARTIALLY_FILLED, OrderStatus.UNKNOWN},
        OrderStatus.UNKNOWN: {OrderStatus.ACKNOWLEDGED, OrderStatus.PARTIALLY_FILLED,
                              OrderStatus.FILLED, OrderStatus.CANCEL_REQUESTED,
                              OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED,
                              OrderStatus.FAILED, OrderStatus.UNKNOWN},
        OrderStatus.FILLED: set(),
        OrderStatus.CANCELED: set(),
        OrderStatus.EXPIRED: set(),
        OrderStatus.REJECTED: set(),
        OrderStatus.FAILED: set(),
    }

    def __init__(self) -> None:
        self._status: dict[str, OrderStatus] = {}

    def register(self, order: Order) -> None:
        if order.client_order_id in self._status:
            raise ValueError("client_order_id already registered")
        if order.quantity <= 0:
            raise ValueError("quantity must be positive")
        self._status[order.client_order_id] = OrderStatus.CREATED

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
