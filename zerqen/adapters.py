from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from .execution import CandleExecutionModel, Fill
from .orders import Order, OrderSide, OrderStatus

class ExchangeAdapter(Protocol):
    def submit(self, order: Order, reference_price: float) -> "AdapterResult": ...
    def cancel(self, client_order_id: str) -> bool: ...

@dataclass(frozen=True)
class AdapterResult:
    client_order_id: str
    status: OrderStatus
    fill: Fill | None
    message: str = ""

class PaperExchangeAdapter:
    """Deterministic paper adapter. It never contacts an exchange."""
    def __init__(self, fee_rate: float = 0.001, slippage_rate: float = 0.0005):
        self.execution = CandleExecutionModel(fee_rate, slippage_rate)
        self._orders: dict[str, AdapterResult] = {}

    def submit(self, order: Order, reference_price: float) -> AdapterResult:
        if order.client_order_id in self._orders:
            return self._orders[order.client_order_id]
        if reference_price <= 0 or order.quantity <= 0:
            result = AdapterResult(order.client_order_id, OrderStatus.REJECTED, None, "invalid order inputs")
        else:
            fill = self.execution.buy(reference_price, order.quantity) if order.side == OrderSide.BUY else self.execution.sell(reference_price, order.quantity)
            result = AdapterResult(order.client_order_id, OrderStatus.FILLED, fill)
        self._orders[order.client_order_id] = result
        return result

    def cancel(self, client_order_id: str) -> bool:
        result = self._orders.get(client_order_id)
        return result is not None and result.status not in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}

@dataclass(frozen=True)
class RestExchangeConfig:
    exchange_id: str
    base_url: str
    testnet_url: str | None = None

class RestExchangeAdapter:
    """Transport-neutral live adapter boundary.

    Concrete exchanges must implement signing and endpoint payload mapping.
    No secrets are accepted in constructor arguments or persisted by this class.
    """

    def __init__(self, config: RestExchangeConfig):
        self.config = config

    def submit(self, order: Order, reference_price: float) -> AdapterResult:
        raise NotImplementedError(f"native adapter required for {self.config.exchange_id}")

    def cancel(self, client_order_id: str) -> bool:
        raise NotImplementedError(f"native adapter required for {self.config.exchange_id}")
