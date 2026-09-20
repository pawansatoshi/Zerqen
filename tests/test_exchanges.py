from zerqen.connection import connection_options, load_credentials
from zerqen.exchanges import ExchangeId, get_exchange

def test_all_supported_exchanges_have_connection_options():
    options = connection_options()
    assert len(options) == 10
    assert {item["id"] for item in options} == {item.value for item in ExchangeId}

def test_okx_requires_passphrase():
    profile = get_exchange(ExchangeId.OKX)
    assert "ZERQEN_OKX_PASSPHRASE" in profile.credential_env

def test_delta_credentials_are_environment_only():
    creds = load_credentials(
        ExchangeId.DELTA_INDIA,
        environ={
            "ZERQEN_DELTA_INDIA_API_KEY": "key",
            "ZERQEN_DELTA_INDIA_API_SECRET": "secret",
        },
    )
    assert creds.values["ZERQEN_DELTA_INDIA_API_KEY"] == "key"

def test_missing_credentials_are_rejected():
    try:
        load_credentials(ExchangeId.BINANCE, environ={})
    except ValueError as exc:
        assert "missing credentials" in str(exc)
    else:
        raise AssertionError("expected missing credentials error")
