from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ledger_migration_defines_authoritative_tables():
    sql = (ROOT / "db" / "migrations" / "002_paper_trade_ledger.sql").read_text()
    for table in ("zerqen_paper_trades", "zerqen_paper_decisions"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    for column in ("gross_exposure", "open_risk", "allocation", "cumulative_pnl"):
        assert f"ADD COLUMN IF NOT EXISTS {column}" in sql


def test_dashboard_has_ledger_compounding_audit_navigation():
    html = (ROOT / "index.html").read_text()
    for label in ("Trade Ledger", "Compounding", "Audit Log"):
        assert label in html
    for view in ('id="ledger"', 'id="compounding"', 'id="audit"'):
        assert view in html


def test_excel_export_contract_contains_all_requested_sheets():
    source = (ROOT / "api" / "ledger.py").read_text()
    for sheet in (
        "Daily Compounding",
        "Trade Ledger",
        "Orders",
        "Fills",
        "Positions",
        "P&L",
        "Risk Events",
        "Equity Snapshots",
        "Audit Log",
    ):
        assert f'"{sheet}"' in source
