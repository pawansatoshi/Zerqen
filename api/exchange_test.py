import json
import os
from http.server import BaseHTTPRequestHandler

EXCHANGES = {
    "binance": "binance", "okx": "okx", "bybit": "bybit", "bitget": "bitget",
    "mexc": "mexc", "kucoin": "kucoin", "gate": "gateio",
    "coindcx": "coindcx", "wazirx": "wazirx", "delta_india": "delta",
}

def send(handler, status, payload):
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        expected = os.environ.get("ZERQEN_DASHBOARD_TOKEN")
        if not expected:
            return send(self, 503, {"ok": False, "error": "dashboard token is not configured"})
        if self.headers.get("x-zerqen-dashboard-token") != expected:
            return send(self, 401, {"ok": False, "error": "unauthorized"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            exchange_id = data["exchange_id"]
            ccxt_id = EXCHANGES[exchange_id]
            api_key = data["api_key"].strip()
            secret = data["api_secret"].strip()
            if not api_key or not secret:
                return send(self, 400, {"ok": False, "error": "api key and secret are required"})
            import ccxt
            config = {"apiKey": api_key, "secret": secret, "enableRateLimit": True}
            if data.get("passphrase"):
                config["password"] = data["passphrase"].strip()
            exchange = getattr(ccxt, ccxt_id)(config)
            mode = data.get("mode", "testnet")
            if mode == "testnet":
                if getattr(exchange, "has", {}).get("sandbox"):
                    exchange.set_sandbox_mode(True)
                else:
                    return send(self, 400, {"ok": False, "error": "testnet/sandbox is not supported by this adapter"})
            exchange.load_markets()
            balance = exchange.fetch_balance()
            result = {
                "ok": True, "exchange": exchange_id, "mode": mode,
                "markets": len(exchange.markets or {}),
                "authenticated": True,
                "balance_assets": len(balance.get("total", {})),
                "trading_test": False,
                "message": "read-only authentication and account access verified; no order was placed",
            }
            return send(self, 200, result)
        except Exception as exc:
            return send(self, 400, {"ok": False, "error": type(exc).__name__ + ": " + str(exc)})
