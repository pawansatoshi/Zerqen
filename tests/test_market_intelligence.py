from zerqen import market_intelligence as mi


def _rows(n=240):
    rows = []
    price = 100.0
    for i in range(n):
        price += 0.05
        rows.append([i, price - 0.5, price + 1.0, price - 1.0, price, 1000.0 + i])
    return rows


def test_report_is_normalized_and_hashed(monkeypatch):
    rows = _rows()
    monkeypatch.setattr(mi, "_fetch_timeframe", lambda exchange, symbol, tf: (rows, {"connectivity_status": "WORKING"}))
    monkeypatch.setattr(mi, "_derivatives", lambda symbol: {"status": "AVAILABLE", "funding_rate": "0"})
    monkeypatch.setattr(mi, "_options", lambda symbol: {"status": "AVAILABLE", "nearest_expiry": 123})
    mi._REPORT_CACHE.clear()
    report = mi.build_report("binance", "BTC/USDT", force=True)
    assert report.report_hash
    assert set(report.timeframes) == {"1h", "4h", "1d"}
    assert report.data_quality["score"] == 1.0
    assert isinstance(mi.report_for_ai(report)["timeframes"], dict)


def test_missing_derivatives_and_options_are_explicit(monkeypatch):
    rows = _rows()
    monkeypatch.setattr(mi, "_fetch_timeframe", lambda exchange, symbol, tf: (rows, {"connectivity_status": "WORKING"}))
    monkeypatch.setattr(mi, "_derivatives", lambda symbol: {"status": "UNAVAILABLE"})
    monkeypatch.setattr(mi, "_options", lambda symbol: {"status": "UNAVAILABLE"})
    mi._REPORT_CACHE.clear()
    report = mi.build_report("binance", "BTC/USDT", force=True)
    assert "futures derivatives context unavailable" in report.warnings
    assert "options expiry context unavailable" in report.warnings


def test_safe_mode_can_be_entered_and_exited(monkeypatch):
    monkeypatch.setenv("ZERQEN_AI_SAFE_MODE", "true")
    monkeypatch.setenv("ZERQEN_AI_SAFE_RETRY_SECONDS", "60")
    monkeypatch.delenv("ZERQEN_AI_DEGRADED_UNTIL", raising=False)
    assert not mi.should_use_safe_mode()
    mi.enter_safe_mode("rate limited")
    assert mi.should_use_safe_mode()
    mi.exit_safe_mode()
    assert not mi.should_use_safe_mode()
