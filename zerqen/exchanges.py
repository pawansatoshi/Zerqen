from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class ExchangeId(StrEnum):
    BINANCE = "binance"
    OKX = "okx"
    BYBIT = "bybit"
    BITGET = "bitget"
    MEXC = "mexc"
    KUCOIN = "kucoin"
    GATE = "gate"
    COINDCX = "coindcx"
    DELTA_INDIA = "delta_india"
    WAZIRX = "wazirx"

@dataclass(frozen=True)
class ExchangeProfile:
    exchange_id: ExchangeId
    display_name: str
    credential_env: tuple[str, ...]
    supports_spot: bool
    supports_derivatives: bool
    adapter: str = "native"

EXCHANGE_PROFILES = {
    ExchangeId.BINANCE: ExchangeProfile(ExchangeId.BINANCE, "Binance", ("ZERQEN_BINANCE_API_KEY", "ZERQEN_BINANCE_API_SECRET"), True, True),
    ExchangeId.OKX: ExchangeProfile(ExchangeId.OKX, "OKX", ("ZERQEN_OKX_API_KEY", "ZERQEN_OKX_API_SECRET", "ZERQEN_OKX_PASSPHRASE"), True, True),
    ExchangeId.BYBIT: ExchangeProfile(ExchangeId.BYBIT, "Bybit", ("ZERQEN_BYBIT_API_KEY", "ZERQEN_BYBIT_API_SECRET"), True, True),
    ExchangeId.BITGET: ExchangeProfile(ExchangeId.BITGET, "Bitget", ("ZERQEN_BITGET_API_KEY", "ZERQEN_BITGET_API_SECRET", "ZERQEN_BITGET_PASSPHRASE"), True, True),
    ExchangeId.MEXC: ExchangeProfile(ExchangeId.MEXC, "MEXC", ("ZERQEN_MEXC_API_KEY", "ZERQEN_MEXC_API_SECRET"), True, True),
    ExchangeId.KUCOIN: ExchangeProfile(ExchangeId.KUCOIN, "KuCoin", ("ZERQEN_KUCOIN_API_KEY", "ZERQEN_KUCOIN_API_SECRET", "ZERQEN_KUCOIN_PASSPHRASE"), True, True),
    ExchangeId.GATE: ExchangeProfile(ExchangeId.GATE, "Gate.io", ("ZERQEN_GATE_API_KEY", "ZERQEN_GATE_API_SECRET"), True, True),
    ExchangeId.COINDCX: ExchangeProfile(ExchangeId.COINDCX, "CoinDCX", ("ZERQEN_COINDCX_API_KEY", "ZERQEN_COINDCX_API_SECRET"), True, True),
    ExchangeId.DELTA_INDIA: ExchangeProfile(ExchangeId.DELTA_INDIA, "Delta Exchange India", ("ZERQEN_DELTA_INDIA_API_KEY", "ZERQEN_DELTA_INDIA_API_SECRET"), True, True),
    ExchangeId.WAZIRX: ExchangeProfile(ExchangeId.WAZIRX, "WazirX", ("ZERQEN_WAZIRX_API_KEY", "ZERQEN_WAZIRX_API_SECRET"), True, True),
}

def list_exchanges() -> tuple[ExchangeProfile, ...]:
    return tuple(EXCHANGE_PROFILES.values())

def get_exchange(exchange_id: str | ExchangeId) -> ExchangeProfile:
    try:
        return EXCHANGE_PROFILES[ExchangeId(exchange_id)]
    except ValueError as exc:
        raise KeyError(f"unsupported exchange: {exchange_id}") from exc
