# Zerqen encrypted exchange vault

Exchange API credentials are entered in the Zerqen website and encrypted before persistent storage.

## What is stored where

- **GitHub:** application source only. Never commit exchange API keys or secrets.
- **Vercel environment:** infrastructure secrets only: `ZERQEN_DASHBOARD_TOKEN`, `ZERQEN_VAULT_KEY`, and `DATABASE_URL`.
- **Postgres/Neon:** encrypted exchange credential ciphertext, nonce, exchange id, mode, and timestamp.
- **Browser:** credentials exist only in the form while the user is entering/testing/saving them. The UI does not use localStorage.

## Required Vercel variables

1. `DATABASE_URL` — your Postgres/Neon connection string.
2. `ZERQEN_DASHBOARD_TOKEN` — long random dashboard access token.
3. `ZERQEN_VAULT_KEY` — long random secret used as the root key for AES-256-GCM encryption.

These are not exchange API credentials. The exchange-specific keys stay out of GitHub and out of per-exchange Vercel variables.

Generate a vault secret with a password generator or a command such as:

```bash
openssl rand -hex 32
```

## Security requirements

- Exchange API keys should have withdrawals disabled.
- Start with read-only permissions.
- Never put exchange secrets in frontend JavaScript, Git history, issue comments, screenshots, or logs.
- Rotate a credential by saving the new key pair; the previous encrypted row is replaced.
- Disconnecting deletes the encrypted credential row.
- The dashboard token is a single-user access gate. A multi-user product should replace it with proper identity/session authentication.
- Persistent automated trading requires a server-side root of trust. A design with literally no server-side secret cannot securely decrypt credentials for unattended execution.

## Database

The API creates the `zerqen_exchange_credentials` table automatically on first request. For production, a dedicated migration should eventually own schema changes.
