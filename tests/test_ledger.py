from datetime import datetime, timezone
from decimal import Decimal

from api.ledger import _filters, _flat_rows, _trade_dict


def test_ledger_filters_are_server_side_and_scoped():
    where, values = _filters({
        "date_from": "2026-09-01",
        "date_to": "2026-09-29",
        "exchange": "okx",
        "symbol": "BTC/USDT",
        "strategy": "PAPER_TEST_HARNESS",
        "side": "buy",
        "status": "CLOSED",
        "q": "trade-123",
    })
    assert "account_id='default'" in where
    assert "entry_timestamp::date >= %s" in where
    assert "entry_timestamp::date <= %s" in where
    assert "exchange_id=%s" in where
    assert "symbol=%s" in where
    assert "strategy=%s" in where
    assert "side=%s" in where
    assert "status=%s" in where
    assert values[:7] == [
        "2026-09-01",
        "2026-09-29",
        "okx",
        "BTC/USDT",
        "PAPER_TEST_HARNESS",
        "buy",
        "CLOSED",
    ]
    assert values[-3:] == ["%trade-123%", "%trade-123%", "%trade-123%"]


def test_trade_dict_serializes_decimal_and_timestamps():
    ts = datetime(2026, 9, 29, tzinfo=timezone.utc)
    row = (
        "trade-1", "signal-1", "entry-1", "exit-1", "fill-1", "fill-2",
        "okx", "BTC/USDT", "1h", "buy", "PAPER_TEST_HARNESS", "trend_up",
        ts, ts, ts,
        Decimal(100), Decimal(110), Decimal(1), Decimal(97), Decimal(106),
        Decimal(5), Decimal(10), Decimal("0.2"), Decimal("0.1"), Decimal(0),
        Decimal("9.7"), Decimal("1.94"), Decimal(10000), Decimal("10009.7"),
        "CLOSED", 60,
    )
    result = _trade_dict(row)
    assert result["entry_price"] == 100.0
    assert result["net_pnl"] == 9.7
    assert result["signal_timestamp"] == ts.isoformat()
    assert result["status"] == "CLOSED"


def test_export_shape_contains_all_authoritative_workbook_sheets():
    data = {
        "daily_compounding": [],
        "trades": [],
        "orders": [],
        "fills": [],
        "positions": [],
        "decisions": [],
        "equity_snapshots": [],
        "audit_log": [],
    }
    sheets = _flat_rows(data)
    assert list(sheets) == [
        "Daily Compounding",
        "Trade Ledger",
        "Orders",
        "Fills",
        "Positions",
        "P&L",
        "Risk Events",
        "Equity Snapshots",
        "Audit Log",
    ]
