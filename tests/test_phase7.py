import json
import pytest
from zerqen.health import system_health
from zerqen.observability import AuditLog
from zerqen.report import build_run_report
from zerqen.telemetry import snapshot

def test_audit_log_is_jsonl():
    log = AuditLog()
    event = log.record("order_filled", "run-1", symbol="BTC/USDT", quantity=1.0)
    parsed = json.loads(event.to_json())
    assert parsed["event"] == "order_filled"
    assert json.loads(log.export_jsonl())["run_id"] == "run-1"

def test_health_blocks_bad_reconciliation():
    status = system_health(data_available=True, execution_available=True, reconciliation_balanced=False, drawdown=0.01, max_drawdown=0.20)
    assert not status.healthy
    assert "reconciliation_balanced" in status.reasons

def test_snapshot():
    item = snapshot(900, 1000, 950, 2, 0.8)
    assert item.drawdown == pytest.approx(0.10)
    assert item.daily_return == pytest.approx(-0.0526315789)

def test_report_round_trip():
    report = build_run_report("run-2", "paper", {"return": 0.1}, {"drawdown": 0.05})
    assert '"run_id": "run-2"' in report.to_json()
