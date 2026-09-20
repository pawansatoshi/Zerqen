from zerqen.exchange_adapters import ADAPTERS, create_exchange_adapter

def test_all_exchange_adapters_registered():
    assert len(ADAPTERS) == 10
    for exchange_id in ADAPTERS:
        adapter = create_exchange_adapter(exchange_id)
        assert adapter.config.exchange_id == exchange_id
        assert adapter.endpoint.startswith("http")

def test_delta_defaults_to_testnet():
    assert "testnet" in create_exchange_adapter("delta_india").endpoint

def test_binance_defaults_to_testnet():
    assert "testnet" in create_exchange_adapter("binance").endpoint
