from zerqen.ccxt_adapter import CCXTExchangeAdapter

def test_live_requires_explicit_flag():
    try:
        CCXTExchangeAdapter("binance", {"apiKey": "x", "secret": "y"}, testnet=False)
    except ValueError as exc:
        assert "live=True" in str(exc)
    else:
        raise AssertionError("live execution must require explicit opt-in")

def test_testnet_and_live_conflict():
    try:
        CCXTExchangeAdapter("binance", {"apiKey": "x", "secret": "y"}, testnet=True, live=True)
    except ValueError:
        pass
    else:
        raise AssertionError("testnet/live conflict must be rejected")
