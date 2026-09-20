import json
import hashlib
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import psycopg

EXCHANGES = {
    "binance": "binance", "okx": "okx", "bybit": "bybit", "bitget": "bitget",
    "mexc": "mexc", "kucoin": "kucoin", "gate": "gateio",
    "coindcx": "coindcx", "wazirx": "wazirx", "delta_india": "delta",
}


def send(handler, status, payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
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
        raise RuntimeError("vault unavailable")
    return hashlib.sha256(secret.encode()).digest()


def load_credential(exchange_id):
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("database unavailable")
    with psycopg.connect(url, connect_timeout=8) as conn:
        row = conn.execute(
            "SELECT mode, nonce, ciphertext FROM zerqen_exchange_credentials WHERE exchange_id = %s",
            (exchange_id,),
        ).fetchone()
    if not row:
        raise LookupError("no saved connection")
    plaintext = AESGCM(vault_key()).decrypt(row[1], row[2], exchange_id.encode())
    return row[0], json.loads(plaintext)


def serialise_trade(t):
    return {
        "id": str(t.get("id") or ""),
        "timestamp": t.get("timestamp"),
        "datetime": t.get("datetime"),
        "symbol": t.get("symbol"),
        "side": t.get("side"),
        "price": t.get("price"),
        "amount": t.get("amount"),
        "cost": t.get("cost"),
        "fee": (t.get("fee") or {}).get("cost"),
        "fee_currency": (t.get("fee") or {}).get("currency"),
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not auth_ok(self):
            return send(self, 401, {"ok": False, "error": "unauthorized"})
        try:
            qs = parse_qs(urlparse(self.path).query)
            exchange_id = qs.get("exchange", [""])[0]
            if exchange_id not in EXCHANGES:
                return send(self, 400, {"ok": False, "error": "unsupported exchange"})

            mode, cred = load_credential(exchange_id)
            import ccxt
            config = {
                "apiKey": cred["api_key"],
                "secret": cred["api_secret"],
                "enableRateLimit": True,
            }
            if cred.get("passphrase"):
                config["password"] = cred["passphrase"]
            exchange = getattr(ccxt, EXCHANGES[exchange_id])(config)
            if mode == "testnet":
                if exchange.has.get("sandbox"):
                    exchange.set_sandbox_mode(True)
                else:
                    return send(self, 400, {"ok": False, "error": "saved connection does not support sandbox mode"})

            exchange.load_markets()
            balance = exchange.fetch_balance()
            total = balance.get("total") or {}
            free = balance.get("free") or {}
            used = balance.get("used") or {}

            positions = []
            if exchange.has.get("fetchPositions"):
                try:
                    raw_positions = exchange.fetch_positions()
                    for p in raw_positions:
                        contracts = float(p.get("contracts") or 0)
                        if contracts:
                            positions.append({
                                "symbol": p.get("symbol"),
                                "side": p.get("side"),
                                "contracts": contracts,
                                "entry": p.get("entryPrice"),
                                "mark": p.get("markPrice") or p.get("lastPrice"),
                                "unrealized": p.get("unrealizedPnl"),
                                "leverage": p.get("leverage"),
                            })
                except Exception:
                    positions = []

            trades = []
            if exchange.has.get("fetchMyTrades"):
                try:
                    raw = exchange.fetch_my_trades(limit=25)
                    trades = [serialise_trade(t) for t in raw]
                except Exception:
                    trades = []

            nonzero = []
            for asset, value in total.items():
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
                if abs(value) > 1e-12:
                    nonzero.append({"asset": asset, "total": value, "free": free.get(asset), "used": used.get(asset)})

            return send(self, 200, {
                "ok": True,
                "exchange": exchange_id,
                "mode": mode,
                "assets": nonzero[:100],
                "positions": positions[:50],
                "trades": trades[:25],
                "server_time": datetime.now(timezone.utc).isoformat(),
            })
        except LookupError:
            return send(self, 404, {"ok": False, "error": "no saved connection"})
        except Exception:
            return send(self, 502, {"ok": False, "error": "account data temporarily unavailable"})

    def log_message(self, format, *args):
        return
