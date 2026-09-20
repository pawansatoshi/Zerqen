import base64
import hashlib
import json
import os
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import psycopg

EXCHANGE_IDS = {
    "delta_india", "coindcx", "binance", "okx", "bybit",
    "bitget", "mexc", "kucoin", "gate", "wazirx",
}

def send(handler, status, payload):
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)

def auth_ok(handler):
    expected = os.environ.get("ZERQEN_DASHBOARD_TOKEN")
    return bool(expected) and handler.headers.get("x-zerqen-dashboard-token") == expected

def vault_key():
    secret = os.environ.get("ZERQEN_VAULT_KEY")
    if not secret:
        raise RuntimeError("ZERQEN_VAULT_KEY is not configured")
    return hashlib.sha256(secret.encode("utf-8")).digest()

def db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    conn = psycopg.connect(url, connect_timeout=8)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zerqen_exchange_credentials (
            exchange_id TEXT PRIMARY KEY,
            mode TEXT NOT NULL CHECK (mode IN ('testnet','live')),
            nonce BYTEA NOT NULL,
            ciphertext BYTEA NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    conn.commit()
    return conn

def encrypt(exchange_id, credentials):
    nonce = os.urandom(12)
    plaintext = json.dumps(credentials, separators=(",", ":")).encode()
    ciphertext = AESGCM(vault_key()).encrypt(nonce, plaintext, exchange_id.encode())
    return nonce, ciphertext

def decrypt(exchange_id, nonce, ciphertext):
    plaintext = AESGCM(vault_key()).decrypt(nonce, ciphertext, exchange_id.encode())
    return json.loads(plaintext)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not auth_ok(self):
            return send(self, 401, {"ok": False, "error": "unauthorized"})
        try:
            with db() as conn:
                rows = conn.execute(
                    "SELECT exchange_id, mode, updated_at FROM zerqen_exchange_credentials ORDER BY exchange_id"
                ).fetchall()
            return send(self, 200, {
                "ok": True,
                "connections": [
                    {"exchange_id": r[0], "mode": r[1], "updated_at": r[2].isoformat()}
                    for r in rows
                ],
            })
        except Exception as exc:
            return send(self, 500, {"ok": False, "error": type(exc).__name__ + ": " + str(exc)})

    def do_POST(self):
        if not auth_ok(self):
            return send(self, 401, {"ok": False, "error": "unauthorized"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            action = data.get("action")
            exchange_id = data.get("exchange_id")
            if exchange_id not in EXCHANGE_IDS:
                return send(self, 400, {"ok": False, "error": "unsupported exchange"})

            with db() as conn:
                if action == "delete":
                    conn.execute(
                        "DELETE FROM zerqen_exchange_credentials WHERE exchange_id = %s",
                        (exchange_id,),
                    )
                    conn.commit()
                    return send(self, 200, {"ok": True, "deleted": exchange_id})

                if action == "save":
                    api_key = str(data.get("api_key", "")).strip()
                    api_secret = str(data.get("api_secret", "")).strip()
                    passphrase = str(data.get("passphrase", "")).strip()
                    mode = data.get("mode", "testnet")
                    if not api_key or not api_secret:
                        return send(self, 400, {"ok": False, "error": "api key and secret are required"})
                    if mode not in {"testnet", "live"}:
                        return send(self, 400, {"ok": False, "error": "invalid mode"})
                    nonce, ciphertext = encrypt(exchange_id, {
                        "api_key": api_key,
                        "api_secret": api_secret,
                        "passphrase": passphrase,
                    })
                    conn.execute(
                        """
                        INSERT INTO zerqen_exchange_credentials
                            (exchange_id, mode, nonce, ciphertext, updated_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (exchange_id) DO UPDATE SET
                            mode = EXCLUDED.mode,
                            nonce = EXCLUDED.nonce,
                            ciphertext = EXCLUDED.ciphertext,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (exchange_id, mode, nonce, ciphertext, datetime.now(timezone.utc)),
                    )
                    conn.commit()
                    return send(self, 200, {"ok": True, "saved": exchange_id, "encrypted": True})

                if action == "get":
                    row = conn.execute(
                        "SELECT mode, nonce, ciphertext FROM zerqen_exchange_credentials WHERE exchange_id = %s",
                        (exchange_id,),
                    ).fetchone()
                    if not row:
                        return send(self, 404, {"ok": False, "error": "no saved credentials"})
                    credentials = decrypt(exchange_id, row[1], row[2])
                    return send(self, 200, {"ok": True, "exchange_id": exchange_id, "mode": row[0], "credentials": credentials})

            return send(self, 400, {"ok": False, "error": "unsupported action"})
        except Exception as exc:
            return send(self, 500, {"ok": False, "error": type(exc).__name__ + ": " + str(exc)})
