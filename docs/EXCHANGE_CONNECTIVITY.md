# Exchange Connectivity

Zerqen now exposes a unified connection registry for ten exchange options:

- Binance
- OKX
- Bybit
- Bitget
- MEXC
- KuCoin
- Gate.io
- CoinDCX
- Delta Exchange India
- WazirX

Each option has a stable ExchangeId, required environment-variable names, and product capability metadata. Secrets are never stored in the repository.

## Credential policy

Use environment variables or a secret manager. Never commit API keys, API secrets, passphrases, or signed request material.

## Adapter policy

The registry is intentionally separate from execution. Selecting an exchange does not automatically enable live trading. Each exchange must have an adapter implementing Zerqen's ExchangeAdapter contract and must pass paper/testnet/demo, reconciliation, rate-limit, retry, and failure-injection tests before live approval.

The architecture supports native adapters and a CCXT-backed adapter for exchanges where that is appropriate. Native implementations remain preferable when exchange-specific order and WebSocket semantics matter.

## India

Delta Exchange India documents REST/WebSocket trading and a demo/testnet endpoint. Its API also supports INR spot products. Zerqen should use those environments before any live capital.

## International

Binance and OKX expose REST/WebSocket trading APIs. Exact product availability, API domains, account modes, and regional restrictions can change; the adapter must validate them at connection time.

## Safety

A connection is not permission to trade. Live execution remains behind Zerqen's mode, risk, kill-switch, approval, and reconciliation controls.
