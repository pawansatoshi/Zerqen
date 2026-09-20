from __future__ import annotations
from .adapters import RestExchangeAdapter, RestExchangeConfig

class DeltaIndiaAdapter(RestExchangeAdapter):
    def __init__(self, testnet: bool = True):
        super().__init__(RestExchangeConfig("delta_india","https://api.india.delta.exchange","https://cdn-ind.testnet.deltaex.org"))
        self.testnet = testnet
    @property
    def endpoint(self) -> str: return self.config.testnet_url if self.testnet else self.config.base_url

class BinanceAdapter(RestExchangeAdapter):
    def __init__(self, testnet: bool = True):
        super().__init__(RestExchangeConfig("binance","https://api.binance.com","https://testnet.binance.vision"))
        self.testnet = testnet
    @property
    def endpoint(self) -> str: return self.config.testnet_url if self.testnet else self.config.base_url

class OKXAdapter(RestExchangeAdapter):
    def __init__(self, demo: bool = True):
        super().__init__(RestExchangeConfig("okx","https://www.okx.com", "https://www.okx.com"))
        self.demo = demo
    @property
    def endpoint(self) -> str: return self.config.base_url

class BybitAdapter(RestExchangeAdapter):
    def __init__(self, testnet: bool = True):
        super().__init__(RestExchangeConfig("bybit","https://api.bybit.com","https://api-testnet.bybit.com"))
        self.testnet = testnet
    @property
    def endpoint(self) -> str: return self.config.testnet_url if self.testnet else self.config.base_url

class BitgetAdapter(RestExchangeAdapter):
    def __init__(self, demo: bool = True):
        super().__init__(RestExchangeConfig("bitget","https://api.bitget.com","https://api.bitget.com"))
        self.demo = demo
    @property
    def endpoint(self) -> str: return self.config.base_url

class MEXCAdapter(RestExchangeAdapter):
    def __init__(self):
        super().__init__(RestExchangeConfig("mexc","https://api.mexc.com",None))
    @property
    def endpoint(self) -> str: return self.config.base_url

class KuCoinAdapter(RestExchangeAdapter):
    def __init__(self):
        super().__init__(RestExchangeConfig("kucoin","https://api.kucoin.com",None))
    @property
    def endpoint(self) -> str: return self.config.base_url

class GateAdapter(RestExchangeAdapter):
    def __init__(self):
        super().__init__(RestExchangeConfig("gate","https://api.gateio.ws",None))
    @property
    def endpoint(self) -> str: return self.config.base_url

class CoinDCXAdapter(RestExchangeAdapter):
    def __init__(self):
        super().__init__(RestExchangeConfig("coindcx","https://api.coindcx.com",None))
    @property
    def endpoint(self) -> str: return self.config.base_url

class WazirXAdapter(RestExchangeAdapter):
    def __init__(self):
        super().__init__(RestExchangeConfig("wazirx","https://api.wazirx.com",None))
    @property
    def endpoint(self) -> str: return self.config.base_url

ADAPTERS = {
    "delta_india": DeltaIndiaAdapter,
    "binance": BinanceAdapter,
    "okx": OKXAdapter,
    "bybit": BybitAdapter,
    "bitget": BitgetAdapter,
    "mexc": MEXCAdapter,
    "kucoin": KuCoinAdapter,
    "gate": GateAdapter,
    "coindcx": CoinDCXAdapter,
    "wazirx": WazirXAdapter,
}

def create_exchange_adapter(exchange_id: str, **kwargs) -> RestExchangeAdapter:
    try:
        return ADAPTERS[exchange_id](**kwargs)
    except KeyError as exc:
        raise ValueError(f"unsupported exchange: {exchange_id}") from exc
