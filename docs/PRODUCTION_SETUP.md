# Zerqen production setup

The dashboard is deployed on Vercel. Exchange credentials are encrypted server-side and are never stored in the repository.

## Required Vercel environment variables

Set these for **Production**:

- `DATABASE_URL` — PostgreSQL/Neon connection string with SSL enabled.
- `ZERQEN_DASHBOARD_TOKEN` — long random admin/dashboard access token.
- `ZERQEN_VAULT_KEY` — separate long random secret used to derive the AES-256-GCM encryption key.

Never commit any of the three values to GitHub.

## Connection workflow

1. Open the Zerqen dashboard.
2. Open **Connections**.
3. Enter the dashboard access token.
4. Enter an exchange API key/secret.
5. Prefer read-only permissions and disable withdrawals.
6. Run **Test connection**.
7. Save the credential. Zerqen stores only encrypted credential material.
8. The account panel polls the connected exchange state every 10 seconds.

## Runtime architecture

- Public BTC market data uses a browser WebSocket for live ticks, with public REST candles and a server fallback.
- Private balances, positions and trades remain server-side.
- Vercel serves the dashboard/API; persistent exchange WebSocket execution workers should run outside serverless request handlers when live execution is enabled.
- Live trading remains guarded and disabled by default.

## Readiness endpoint

`/api/health` reports whether the three required infrastructure variables are configured without exposing their values.
