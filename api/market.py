from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from zerqen.exchange_adapters import create_exchange_adapter
from zerqen.exchanges import get_exchange

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


def classify_error(exc):
    name = type(exc).__name__
    if name in {"RequestTimeout", "ExchangeNotAvailable", "DDoSProtection", "RateLimitExceeded", "NetworkError"}:
        return "DEGRADED", name
    if name in {"NotSupported", "BadSymbol"}:
        return "NOT_SUPPORTED", name
    return "FAILED", name


def public_market_probe(exchange_id, symbol, timeframe, limit):
    profile = get_exchange(exchange_id)
    adapter = create_exchange_adapter(exchange_id, testnet=False) if exchange_id in {"binance", "bybit", "delta_india"} else create_exchange_adapter(exchange_id)
    ccxt_id = EXCHANGES[exchange_id]

    import ccxt

    exchange = getattr(ccxt, ccxt_id)({"enableRateLimit": True, "timeout": 8000})
    stage = "load_markets"
    try:
        exchange.load_markets()
        symbol_supported = symbol in exchange.symbols
        if not symbol_supported:
            return {
                "ok": False,
                "connectivity_status": "NOT_SUPPORTED",
                "exchange": exchange_id,
                "adapter": type(adapter).__name__,
                "profile": profile.display_name,
                "public_api": adapter.endpoint,
                "symbol": symbol,
                "symbol_mapping": False,
                "ticker": False,
                "ohlcv": False,
                "error_type": "BadSymbol",
                "error_stage": "symbol_mapping",
            }

        stage = "fetch_ticker"
        ticker_raw = exchange.fetch_ticker(symbol)
        ticker = {
            "last": ticker_raw.get("last"),
            "bid": ticker_raw.get("bid"),
            "ask": ticker_raw.get("ask"),
            "change": ticker_raw.get("percentage"),
            "quote_volume": ticker_raw.get("quoteVolume"),
            "timestamp": ticker_raw.get("timestamp"),
        }

        stage = "fetch_ohlcv"
        rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not rows:
            return {
                "ok": False,
                "connectivity_status": "DEGRADED",
                "exchange": exchange_id,
                "adapter": type(adapter).__name__,
                "profile": profile.display_name,
                "public_api": adapter.endpoint,
                "symbol": symbol,
                "symbol_mapping": True,
                "ticker": True,
                "ohlcv": False,
                "ticker_data": ticker,
                "error_type": "NoMarketData",
                "error_stage": "fetch_ohlcv",
            }

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
            rolling = sum(trs[1 : period + 1]) / period
            atr[period] = rolling
            for i in range(period + 1, len(trs)):
                rolling = (rolling * (period - 1) + trs[i]) / period
                atr[i] = rolling

        status = "WORKING"
        if ticker.get("last") is None or len(rows) < min(limit, 20):
            status = "DEGRADED"

        return {
            "ok": status == "WORKING",
            "connectivity_status": status,
            "exchange": exchange_id,
            "adapter": type(adapter).__name__,
            "profile": profile.display_name,
            "public_api": adapter.endpoint,
            "symbol": symbol,
            "symbol_mapping": True,
            "ticker": True,
            "ohlcv": True,
            "times": times,
            "closes": closes,
            "volumes": volumes,
            "ema9": ema(closes, 9),
            "ema21": ema(closes, 21),
            "rsi": rsi(closes),
            "atr": atr,
            "ticker_data": ticker,
            "source": "public exchange market data via CCXT",
        }
    except Exception as exc:  # noqa: BLE001
        status, error_type = classify_error(exc)
        return {
            "ok": False,
            "connectivity_status": status,
            "exchange": exchange_id,
            "adapter": type(adapter).__name__,
            "profile": profile.display_name,
            "public_api": adapter.endpoint,
            "symbol": symbol,
            "symbol_mapping": stage != "load_markets",
            "ticker": stage == "fetch_ohlcv",
            "ohlcv": False,
            "error_type": error_type,
            "error_stage": stage,
        }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            exchange_id = qs.get("exchange", ["binance"])[0]
            symbol = qs.get("symbol", ["BTC/USDT"])[0]
            timeframe = qs.get("timeframe", ["1h"])[0]
            limit = min(max(int(qs.get("limit", ["120"])[0]), 20), 200)

            if exchange_id not in EXCHANGES:
                return send(self, 400, {"ok": False, "error": "unsupported exchange"})

            result = public_market_probe(exchange_id, symbol, timeframe, limit)
            http_status = 200 if result["connectivity_status"] in {"WORKING", "DEGRADED"} else 502
            return send(self, http_status, result)
        except ValueError:
            return send(self, 400, {"ok": False, "error": "invalid market query"})
        except Exception:  # noqa: BLE001
            return send(self, 502, {"ok": False, "error": "market data temporarily unavailable"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        return
