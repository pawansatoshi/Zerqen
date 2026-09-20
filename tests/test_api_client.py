from zerqen.api_client import (
    bitget_signature, delta_signature, gate_signature, okx_signature,
    wazirx_signature,
)

def test_signatures_are_deterministic():
    assert delta_signature("secret", "POST", "/v2/orders", "123", "{}")
    assert okx_signature("secret", "2026-01-01T00:00:00.000Z", "POST", "/api/v5/trade/order", "{}")
    assert bitget_signature("secret", "123", "POST", "/api/v3/trade/place-order", body="{}")
    assert gate_signature("secret", "POST", "/api/v4/spot/orders", "", "{}", "123")
    assert wazirx_signature("secret", {"symbol": "btcinr", "timestamp": 123})

def test_signatures_change_with_payload():
    assert delta_signature("secret", "POST", "/v2/orders", "123", "{}") != delta_signature(
        "secret", "POST", "/v2/orders", "123", '{"x":1}'
    )
