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

    def submit_once(self, order: Order, reference_price: float) -> ExecutionResult:
        duplicate = False
        try:
            self.state.register(order)
        except ValueError as exc:
            if "already registered" not in str(exc):
                raise
            duplicate = True

        if duplicate:
            current = self.state.status(order.client_order_id)
            return ExecutionResult(
                OrderEvent(order.client_order_id, current, 0.0, 0.0, "duplicate submission suppressed"),
                True,
            )

        self.state.transition(order.client_order_id, OrderStatus.RISK_CHECK)
        self.state.transition(order.client_order_id, OrderStatus.APPROVED)
        self.state.transition(order.client_order_id, OrderStatus.SUBMITTED)

        try:
            result = self.adapter.submit(order, reference_price)
        except Exception as exc:
            self.state.transition(order.client_order_id, OrderStatus.UNKNOWN)
            return ExecutionResult(
                OrderEvent(order.client_order_id, OrderStatus.UNKNOWN, 0.0, 0.0, f"submission outcome unknown: {type(exc).__name__}"),
                False,
            )

        if result.status == OrderStatus.FILLED:
            self.state.transition(order.client_order_id, OrderStatus.ACKNOWLEDGED)
        elif result.status not in {OrderStatus.UNKNOWN, OrderStatus.REJECTED, OrderStatus.FAILED}:
            self.state.transition(order.client_order_id, OrderStatus.ACKNOWLEDGED)

        current = self.state.status(order.client_order_id)
        if current != result.status:
            self.state.transition(order.client_order_id, result.status)

        fill = result.fill
        return ExecutionResult(
            OrderEvent(
                order.client_order_id,
                result.status,
                fill.quantity if fill else 0.0,
                fill.price if fill else 0.0,
                result.message,
            ),
            False,
        )
