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
    "gate": "gate",
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


def _http_json(url):
    import urllib.request

    with urllib.request.urlopen(url, timeout=8) as response:
        return json.loads(response.read().decode())


def _native_result(exchange_id, adapter, profile, symbol, rows, ticker_data):
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
            "ticker": ticker_data is not None,
            "ohlcv": False,
            "error_type": "NoMarketData",
            "error_stage": "fetch_ohlcv",
        }

    rows = sorted(rows, key=lambda r: int(r[0]))
    closes = [float(r[4]) for r in rows]
    times = [int(r[0]) if int(r[0]) > 10**12 else int(r[0]) * 1000 for r in rows]
    volumes = [float(r[5]) for r in rows]

    def ema(values, period):
        k = 2.0 / (period + 1.0)
        out = []
        value = values[0]
        for x in values:
            value = x if not out else x * k + value * (1 - k)
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
                    avg_gain, avg_loss = gains / period, losses / period
                    out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
            else:
                avg_gain = (avg_gain * (period - 1) + gain) / period
                avg_loss = (avg_loss * (period - 1) + loss) / period
                out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
        return out

    trs = []
    for i, row in enumerate(rows):
        high, low = float(row[2]), float(row[3])
        prev_close = closes[i - 1] if i else closes[i]
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    atr = [None] * len(rows)
    period = 14
    if len(trs) > period:
        rolling = sum(trs[1:period + 1]) / period
        atr[period] = rolling
        for i in range(period + 1, len(trs)):
            rolling = (rolling * (period - 1) + trs[i]) / period
            atr[i] = rolling

    status = "WORKING"
    if ticker_data is None or len(rows) < 20:
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
        "ticker": ticker_data is not None,
        "ohlcv": True,
        "times": times,
        "closes": closes,
        "volumes": volumes,
        "ema9": ema(closes, 9),
        "ema21": ema(closes, 21),
        "rsi": rsi(closes),
        "atr": atr,
        "ticker_data": ticker_data,
        "source": "public exchange market data via native public API",
    }


def native_market_probe(exchange_id, symbol, timeframe, limit):
    profile = get_exchange(exchange_id)
    adapter = create_exchange_adapter(exchange_id)
    base_symbol = symbol.replace("/", "").upper()

    if exchange_id == "coindcx":
        markets = _http_json("https://api.coindcx.com/exchange/v1/markets_details")
        market = next(
            (
                m for m in markets
                if str(m.get("base_currency_short_name", "")).upper()
                + str(m.get("target_currency_short_name", "")).upper()
                == base_symbol
            ),
            None,
        )
        if not market:
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
        pair = market["pair"]
        tickers = _http_json("https://api.coindcx.com/exchange/ticker")
        raw_ticker = next((t for t in tickers if str(t.get("market", "")).upper() == base_symbol), None)
        ticker = None if raw_ticker is None else {
            "last": float(raw_ticker["last_price"]),
            "bid": float(raw_ticker["bid"]),
            "ask": float(raw_ticker["ask"]),
            "change": float(raw_ticker.get("change_24_hour", 0)),
            "quote_volume": float(raw_ticker.get("volume", 0)),
            "timestamp": int(raw_ticker.get("timestamp", 0)),
        }
        rows_raw = _http_json(
            "https://api.coindcx.com/market_data/candles?"
            + urllib.parse.urlencode({"pair": pair, "interval": timeframe, "limit": limit})
        )
        rows = [
            [r["time"], r["open"], r["high"], r["low"], r["close"], r["volume"]]
            for r in rows_raw
        ]
        return _native_result(exchange_id, adapter, profile, symbol, rows, ticker)

    info = _http_json("https://api.wazirx.com/sapi/v1/exchangeInfo")
    wanted = base_symbol.lower()
    market = next((m for m in info.get("symbols", []) if str(m.get("symbol", "")).lower() == wanted), None)
    if not market:
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
    query_symbol = market["symbol"].lower()
    raw_ticker = _http_json(
        "https://api.wazirx.com/sapi/v1/ticker/24hr?"
        + urllib.parse.urlencode({"symbol": query_symbol})
    )
    ticker = {
        "last": float(raw_ticker["lastPrice"]),
        "bid": float(raw_ticker["bidPrice"]),
        "ask": float(raw_ticker["askPrice"]),
        "change": (
            (float(raw_ticker["lastPrice"]) - float(raw_ticker["openPrice"]))
            / float(raw_ticker["openPrice"]) * 100
            if float(raw_ticker["openPrice"]) else None
        ),
        "quote_volume": float(raw_ticker.get("volume", 0)),
        "timestamp": int(raw_ticker.get("at", 0)) * 1000,
    }
    rows_raw = _http_json(
        "https://api.wazirx.com/sapi/v1/klines?"
        + urllib.parse.urlencode({"symbol": query_symbol, "interval": timeframe, "limit": limit})
    )
    return _native_result(exchange_id, adapter, profile, symbol, rows_raw, ticker)


def public_market_probe(exchange_id, symbol, timeframe, limit):
    if exchange_id in {"coindcx", "wazirx"}:
        try:
            return native_market_probe(exchange_id, symbol, timeframe, limit)
        except Exception as exc:  # noqa: BLE001
            profile = get_exchange(exchange_id)
            adapter = create_exchange_adapter(exchange_id)
            return {
                "ok": False,
                "connectivity_status": "FAILED",
                "exchange": exchange_id,
                "adapter": type(adapter).__name__,
                "profile": profile.display_name,
                "public_api": adapter.endpoint,
                "symbol": symbol,
                "symbol_mapping": False,
                "ticker": False,
                "ohlcv": False,
                "error_type": type(exc).__name__,
                "error_stage": "public_api",
            }

    profile = get_exchange(exchange_id)
    adapter = create_exchange_adapter(exchange_id, testnet=False) if exchange_id in {"binance", "bybit", "delta_india"} else create_exchange_adapter(exchange_id)
    ccxt_id = EXCHANGES[exchange_id]
    stage = "load_markets"
    try:
        import ccxt

        exchange = getattr(ccxt, ccxt_id)({"enableRateLimit": True, "timeout": 8000})
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
        if stage == "load_markets" and status == "DEGRADED":
            status = "FAILED"
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
