# Zerqen Vercel Exchange Dashboard

The repository now contains a Vercel-ready connection dashboard at the root path.

## Setup

1. Import pawansatoshi/Zerqen into Vercel.
2. Add the Vercel environment variable ZERQEN_DASHBOARD_TOKEN.
3. Redeploy.
4. Open the deployment URL.
5. Select one exchange.
6. Enter the dashboard token and exchange API credentials.
7. Start with Testnet/Demo where supported.
8. Press Test connection.

The endpoint performs read-only authentication/account access verification. It does not place orders.

## API permissions

Use exchange API keys with withdrawals disabled. Prefer read-only permissions for the connection test. Trading permissions should only be granted when a later, separately guarded execution workflow is intentionally enabled.

## Secret handling

API secrets are sent only to the server-side Vercel function over HTTPS. They are not written to GitHub or stored by the dashboard. Do not put exchange credentials into frontend source code, committed environment files, or browser local storage.

## Current limitation

The dashboard verifies authentication and account access through CCXT. Exchange-specific testnet/demo availability differs. A successful connection test is not proof that live order execution, WebSocket fills, symbol precision, funding, or reconciliation are production-ready. Those behaviors must be validated separately for each exchange before live approval.
