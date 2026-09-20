from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .orders import Order, OrderSide, OrderStatus
from .adapters import AdapterResult, ExchangeAdapter

@dataclass(frozen=True)
class NormalizedOrder:
    exchange_order_id: str
    client_order_id: str
    status: OrderStatus
    filled_quantity: float
    average_price: float
    raw: dict[str, Any]

_STATUS_MAP = {
    "open": OrderStatus.SUBMITTED, "new": OrderStatus.SUBMITTED, "pending": OrderStatus.SUBMITTED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED, "closed": OrderStatus.FILLED,
    "filled": OrderStatus.FILLED, "canceled": OrderStatus.CANCELED,
    "cancelled": OrderStatus.CANCELED, "rejected": OrderStatus.REJECTED,
}

class CCXTExchangeAdapter(ExchangeAdapter):
    def __init__(self, exchange_id: str, credentials: dict[str, str], *, testnet: bool = True, live: bool = False):
        if live is False and testnet is False:
            raise ValueError("set live=True explicitly for non-testnet execution")
        if live and testnet:
            raise ValueError("testnet and live cannot both be enabled")
        try:
            import ccxt
        except ImportError as exc:
            raise RuntimeError("ccxt dependency is required for CCXT adapters") from exc
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"CCXT does not expose exchange: {exchange_id}")
        klass = getattr(ccxt, exchange_id)
        config = {"apiKey": credentials.get("apiKey"), "secret": credentials.get("secret")}
        if credentials.get("password"):
            config["password"] = credentials["password"]
        self.exchange = klass(config)
        self.exchange.enableRateLimit = True
        if testnet and hasattr(self.exchange, "set_sandbox_mode"):
            self.exchange.set_sandbox_mode(True)
        self.exchange_id, self.testnet, self.live = exchange_id, testnet, live

    @staticmethod
    def _status(status: str | None) -> OrderStatus:
        return _STATUS_MAP.get((status or "").lower(), OrderStatus.REJECTED)

    def submit(self, order: Order, reference_price: float) -> AdapterResult:
        if reference_price <= 0 or order.quantity <= 0:
            return AdapterResult(order.client_order_id, OrderStatus.REJECTED, None, "invalid order")
        side = "buy" if order.side == OrderSide.BUY else "sell"
        params = {"clientOrderId": order.client_order_id}
        result = self.exchange.create_order(
            order.symbol, order.order_type, side, order.quantity,
            reference_price if order.order_type.lower() == "limit" else None, params,
        )
        status = self._status(result.get("status"))
        filled = float(result.get("filled") or 0.0)
        price = float(result.get("average") or result.get("price") or reference_price)
        from .execution import Fill
        fill = Fill(price, filled, 0.0) if filled > 0 else None
        return AdapterResult(order.client_order_id, status, fill, str(result.get("info", "")))

    def cancel(self, client_order_id: str) -> bool:
        raise NotImplementedError("cancel requires symbol on exchanges using unified cancel_order")

    def fetch_order(self, exchange_order_id: str, symbol: str) -> NormalizedOrder:
        result = self.exchange.fetch_order(exchange_order_id, symbol)
        return NormalizedOrder(str(result.get("id", exchange_order_id)),
            str(result.get("clientOrderId") or result.get("client_order_id") or ""),
            self._status(result.get("status")), float(result.get("filled") or 0.0),
            float(result.get("average") or result.get("price") or 0.0), result)

    def fetch_balance(self) -> dict[str, Any]:
        return self.exchange.fetch_balance()

    def fetch_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        return self.exchange.fetch_open_orders(symbol)

    def fetch_positions(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        if not self.exchange.has.get("fetchPositions"):
            return []
        return self.exchange.fetch_positions(symbols)
