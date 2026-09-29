# Zerqen Exchange Verification Matrix

Date: 2026-09-29
Branch: audit/production-hardening-2026-09-29

This matrix records code-level capability only until authenticated runtime evidence exists. Adapter registration is not connectivity proof. Live production execution remains OFF.

| Exchange | Adapter | Auth | Read | Balance | Orders | Positions | Testnet/Sandbox | Order test | Cancel | Reconciliation | Production |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Binance | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | CAPABILITY EXISTS | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |
| OKX | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | CAPABILITY MUST BE RUNTIME VERIFIED | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |
| Bybit | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | CAPABILITY EXISTS | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |
| Bitget | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | CAPABILITY MUST BE RUNTIME VERIFIED | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |
| MEXC | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | NO VERIFIED SANDBOX EVIDENCE | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |
| KuCoin | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | NO VERIFIED SANDBOX EVIDENCE | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |
| Gate | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | NO VERIFIED SANDBOX EVIDENCE | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |
| Delta India | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | Native endpoint boundary present | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |
| CoinDCX | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | NO VERIFIED SANDBOX EVIDENCE | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |
| WazirX | PRESENT | CCXT path | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | NO VERIFIED SANDBOX EVIDENCE | NOT RUN | NOT RUN | NOT VERIFIED | NOT VERIFIED |

## Evidence rules

- PRESENT means the repository contains the adapter/registry entry.
- IMPLEMENTED means the current CCXT/API control plane contains a code path.
- NOT RUN means no authenticated exchange action has been executed by this implementation session.
- NOT VERIFIED means production readiness must not be inferred.
- Sandbox availability is exchange-specific and must be confirmed against the actual adapter/provider at runtime.
- No exchange is marked production verified by documentation alone.

## Required next evidence

For each exchange, collect:
1. authentication success
2. market read
3. balance read
4. positions/open-orders read where supported
5. controlled testnet order where an official sandbox exists
6. acknowledgement/status
7. fill/cancel handling
8. reconciliation
9. failure injection
10. restart recovery

Until those records exist, live execution stays disabled.
