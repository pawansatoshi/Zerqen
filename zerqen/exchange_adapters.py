from zerqen.adapters import RestExchangeAdapter, RestExchangeConfig

class DeltaIndiaAdapter(RestExchangeAdapter):
    """Delta Exchange India adapter boundary; signing/HTTP transport is next."""
    def __init__(self, testnet: bool = True):
        super().__init__(RestExchangeConfig(
            "delta_india",
            "https://api.india.delta.exchange",
            "https://cdn-ind.testnet.deltaex.org",
        ))
        self.testnet = testnet

    @property
    def endpoint(self) -> str:
        return self.config.testnet_url if self.testnet else self.config.base_url
