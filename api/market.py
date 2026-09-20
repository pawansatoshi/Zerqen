import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


EXCHANGES = {
    "binance": "binance",
    "okx": "okx",
    "bybit": "bybit",
    "bitget": "bitget",
    "mexc": "mexc",
    "kucoin": "kucoin",
    "gate": "gateio",
    "coindcx": "coindcx",
    "wazirx": "wazirx",
    "delta_india": "delta",
}


def send(handler, status, payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            exchange_id = qs.get("exchange", ["binance"])[0]
            symbol = qs.get("symbol", ["BTC/USDT"])[0]
            timeframe = qs.get("timeframe", ["1h"])[0]
            limit = min(max(int(qs.get("limit", ["120"])[0]), 20), 200)

            ccxt_id = EXCHANGES.get(exchange_id)
            if not ccxt_id:
                return send(self, 400, {"ok": False, "error": "unsupported exchange"})

            import ccxt
            exchange = getattr(ccxt, ccxt_id)({"enableRateLimit": True})
            if not exchange.has.get("fetchOHLCV"):
                return send(self, 400, {"ok": False, "error": "market candles are not supported by this exchange"})

            exchange.load_markets()
            if symbol not in exchange.symbols:
                return send(self, 400, {"ok": False, "error": "symbol is not available on this exchange"})

            rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not rows:
                return send(self, 502, {"ok": False, "error": "no market data returned"})

            closes = [float(r[4]) for r in rows]
            times = [int(r[0]) for r in rows]
            volumes = [float(r[5]) for r in rows]

            def ema(values, period):
                k = 2.0 / (period + 1.0)
                out = []
                value = values[0]
                for x in values:
                    value = x if not out else (x * k + value * (1 - k))
                    out.append(value)
                return out

            def rsi(values, period=14):
                out = [None] * len(values)
                gains = losses = 0.0
                for i in range(1, len(values)):
                    change = values[i] - values[i - 1]
                    gain, loss = max(change, 0.0), max(-change, 0.0)
                    if i <= period:
                        gains += gain
                        losses += loss
                        if i == period:
                            avg_gain = gains / period
                            avg_loss = losses / period
                            out[i] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
                    else:
                        avg_gain = (avg_gain * (period - 1) + gain) / period
                        avg_loss = (avg_loss * (period - 1) + loss) / period
                        out[i] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
                return out

            atr = [None] * len(rows)
            period = 14
            trs = []
            for i, row in enumerate(rows):
                high, low = float(row[2]), float(row[3])
                prev_close = closes[i - 1] if i else closes[i]
                trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
            if len(trs) > period:
                rolling = sum(trs[1:period + 1]) / period
                atr[period] = rolling
                for i in range(period + 1, len(trs)):
                    rolling = (rolling * (period - 1) + trs[i]) / period
                    atr[i] = rolling

            return send(self, 200, {
                "ok": True,
                "exchange": exchange_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "times": times,
                "closes": closes,
                "volumes": volumes,
                "ema9": ema(closes, 9),
                "ema21": ema(closes, 21),
                "rsi": rsi(closes),
                "atr": atr,
                "source": "public exchange market data",
            })
        except ValueError:
            return send(self, 400, {"ok": False, "error": "invalid market query"})
        except Exception:
            return send(self, 502, {"ok": False, "error": "market data temporarily unavailable"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        return
