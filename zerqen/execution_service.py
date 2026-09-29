from __future__ import annotations
from dataclasses import dataclass
from .adapters import ExchangeAdapter
from .orders import Order, OrderEvent, OrderStateMachine, OrderStatus


@dataclass(frozen=True)
class ExecutionResult:
    event: OrderEvent
    duplicate: bool = False


class ExecutionService:
    """Execution boundary: authorization must happen before this service."""

    def __init__(self, adapter: ExchangeAdapter):
        self.adapter = adapter
        self.state = OrderStateMachine()
        self._events: dict[str, OrderEvent] = {}

    def submit_once(self, order: Order, reference_price: float) -> ExecutionResult:
        try:
            self.state.register(order)
        except ValueError as exc:
            if "already registered" not in str(exc):
                raise
            event = self._events.get(order.client_order_id)
            if event is None:
                current = self.state.status(order.client_order_id)
                event = OrderEvent(order.client_order_id, current, 0.0, 0.0, "duplicate submission suppressed")
            return ExecutionResult(event, True)

        self.state.transition(order.client_order_id, OrderStatus.RISK_CHECK)
        self.state.transition(order.client_order_id, OrderStatus.APPROVED)
        self.state.transition(order.client_order_id, OrderStatus.SUBMITTED)

        try:
            result = self.adapter.submit(order, reference_price)
        except Exception as exc:  # noqa: BLE001
            self.state.transition(order.client_order_id, OrderStatus.UNKNOWN)
            event = OrderEvent(
                order.client_order_id, OrderStatus.UNKNOWN, 0.0, 0.0,
                f"submission outcome unknown: {type(exc).__name__}",
            )
            self._events[order.client_order_id] = event
            return ExecutionResult(event)

        if result.status not in {OrderStatus.UNKNOWN, OrderStatus.REJECTED, OrderStatus.FAILED}:
            self.state.transition(order.client_order_id, OrderStatus.ACKNOWLEDGED)

        current = self.state.status(order.client_order_id)
        if current != result.status:
            self.state.transition(order.client_order_id, result.status)

        fill = result.fill
        event = OrderEvent(
            order.client_order_id,
            result.status,
            fill.quantity if fill else 0.0,
            fill.price if fill else 0.0,
            result.message,
        )
        self._events[order.client_order_id] = event
        return ExecutionResult(event)
