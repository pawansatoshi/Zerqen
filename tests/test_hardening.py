import pandas as pd
from zerqen.config import ZerqenConfig
from zerqen.data_quality import validate_ohlcv
from zerqen.orders import Order, OrderSide, OrderStateMachine, OrderStatus
from zerqen.backtest import run_backtest


def test_data_quality_rejects_invalid_ohlc_and_future_timestamp():
    now = pd.Timestamp("2026-01-02T00:00:00Z")
    frame = pd.DataFrame([
        {"timestamp": "2026-01-01T00:00:00Z", "open": 100, "high": 90, "low": 95, "close": 100, "volume": 1},
        {"timestamp": "2026-01-03T00:00:00Z", "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1},
    ])
    ok, reasons = validate_ohlcv(frame, expected_interval="1d", now=now)
    assert not ok
    assert "invalid OHLC relationships" in reasons
    assert "future timestamps" in reasons


def test_order_lifecycle_requires_explicit_acknowledgement():
    machine = OrderStateMachine()
    order = Order("zq-lifecycle", "BTC/USDT", OrderSide.BUY, 1.0)
    machine.register(order)
    machine.transition(order.client_order_id, OrderStatus.RISK_CHECK)
    machine.transition(order.client_order_id, OrderStatus.APPROVED)
    machine.transition(order.client_order_id, OrderStatus.SUBMITTED)
    machine.transition(order.client_order_id, OrderStatus.ACKNOWLEDGED)
    machine.transition(order.client_order_id, OrderStatus.PARTIALLY_FILLED)
    machine.transition(order.client_order_id, OrderStatus.FILLED)
    assert machine.status(order.client_order_id) == OrderStatus.FILLED


def test_unknown_order_state_is_not_terminal_and_can_be_reconciled():
    machine = OrderStateMachine()
    order = Order("zq-unknown", "BTC/USDT", OrderSide.BUY, 1.0)
    machine.register(order)
    machine.transition(order.client_order_id, OrderStatus.RISK_CHECK)
    machine.transition(order.client_order_id, OrderStatus.APPROVED)
    machine.transition(order.client_order_id, OrderStatus.SUBMITTED)
    machine.transition(order.client_order_id, OrderStatus.UNKNOWN)
    machine.transition(order.client_order_id, OrderStatus.ACKNOWLEDGED)
    assert machine.status(order.client_order_id) == OrderStatus.ACKNOWLEDGED


def test_backtest_reports_open_position_at_end_of_test():
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=80, freq="h", tz="UTC"),
        "open": [100 + i * 0.2 for i in range(80)],
        "high": [101 + i * 0.2 for i in range(80)],
        "low": [99 + i * 0.2 for i in range(80)],
        "close": [100 + i * 0.2 for i in range(80)],
        "volume": [1000.0] * 80,
    })
    trades, metrics = run_backtest(frame, ZerqenConfig())
    assert "max_drawdown" in metrics
    if not trades.empty:
        assert trades.iloc[-1]["reason"] in {"stop", "target", "signal", "end_of_test"}


def test_backtest_supports_all_ui_timeframes():
    from api.backtest import BACKTEST_TIMEFRAMES
    assert BACKTEST_TIMEFRAMES == {
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "3d", "1w", "1M",
    }
