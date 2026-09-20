from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Zerqen API", version="0.1.0")


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


def safe_error(message: str) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=502)


def require_dashboard_token(token: str | None) -> None:
    expected = os.environ.get("ZERQEN_DASHBOARD_TOKEN")
    if not expected:
        raise HTTPException(503, "dashboard authentication is not configured")
    if token != expected:
        raise HTTPException(401, "unauthorized")


def vault_key() -> bytes:
    secret = os.environ.get("ZERQEN_VAULT_KEY")
    if not secret:
        raise RuntimeError("vault is not configured")
    return hashlib.sha256(secret.encode()).digest()


def get_db():
    import psycopg

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("database is not configured")
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


def encrypt_credentials(exchange_id: str, credentials: dict[str, str]) -> tuple[bytes, bytes]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    plaintext = json.dumps(credentials, separators=(",", ":")).encode()
    ciphertext = AESGCM(vault_key()).encrypt(nonce, plaintext, exchange_id.encode())
    return nonce, ciphertext


def decrypt_credentials(exchange_id: str, nonce: bytes, ciphertext: bytes) -> dict[str, str]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    plaintext = AESGCM(vault_key()).decrypt(nonce, ciphertext, exchange_id.encode())
    return json.loads(plaintext)


def load_credential(exchange_id: str) -> tuple[str, dict[str, str]]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT mode, nonce, ciphertext FROM zerqen_exchange_credentials WHERE exchange_id=%s",
            (exchange_id,),
        ).fetchone()
    if not row:
        raise LookupError("no saved connection")
    return row[0], decrypt_credentials(exchange_id, row[1], row[2])


def make_exchange(exchange_id: str, credentials: dict[str, str] | None = None):
    import ccxt

    ccxt_id = EXCHANGES.get(exchange_id)
    if not ccxt_id:
        raise ValueError("unsupported exchange")

    config: dict[str, Any] = {"enableRateLimit": True, "timeout": 8000}
    if credentials:
        config.update({"apiKey": credentials["api_key"], "secret": credentials["api_secret"]})
        if credentials.get("passphrase"):
            config["password"] = credentials["passphrase"]
    return getattr(ccxt, ccxt_id)(config)


def compute_indicators(rows: list[list[Any]]) -> dict[str, list[Any]]:
    closes = [float(r[4]) for r in rows]
    volumes = [float(r[5]) for r in rows]

    def ema(values: list[float], period: int) -> list[float]:
        k = 2.0 / (period + 1.0)
        out: list[float] = []
        value = values[0]
        for x in values:
            value = x if not out else x * k + value * (1 - k)
            out.append(value)
        return out

    def rsi(values: list[float], period: int = 14) -> list[float | None]:
        out: list[float | None] = [None] * len(values)
        gains = losses = 0.0
        avg_gain = avg_loss = 0.0
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

    trs: list[float] = []
    atr: list[float | None] = [None] * len(rows)
    for i, row in enumerate(rows):
        high, low = float(row[2]), float(row[3])
        prev_close = closes[i - 1] if i else closes[i]
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    period = 14
    if len(trs) > period:
        rolling = sum(trs[1 : period + 1]) / period
        atr[period] = rolling
        for i in range(period + 1, len(trs)):
            rolling = (rolling * (period - 1) + trs[i]) / period
            atr[i] = rolling

    return {
        "times": [int(r[0]) for r in rows],
        "opens": [float(r[1]) for r in rows],
        "highs": [float(r[2]) for r in rows],
        "lows": [float(r[3]) for r in rows],
        "closes": closes,
        "volumes": volumes,
        "ema9": ema(closes, 9),
        "ema21": ema(closes, 21),
        "rsi": rsi(closes),
        "atr": atr,
    }


@app.get("/")
def home():
    return FileResponse(Path(__file__).resolve().parent.parent / "index.html")


@app.get("/api")
def api_home():
    return {
        "ok": True,
        "service": "zerqen",
        "version": "0.1.0",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/health")
def health():
    token_configured = bool(os.environ.get("ZERQEN_DASHBOARD_TOKEN"))
    vault_configured = bool(os.environ.get("ZERQEN_VAULT_KEY"))
    database_configured = bool(os.environ.get("DATABASE_URL"))
    configured = token_configured and vault_configured and database_configured
    return {
        "ok": configured,
        "service": "zerqen",
        "market_data": "public REST + browser WebSocket",
        "execution": "guarded",
        "live_trading_default": False,
        "configuration": {
            "dashboard_auth": token_configured,
            "credential_vault": vault_configured,
            "database": database_configured,
        },
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/market")
def market(
    exchange: str = Query("binance"),
    symbol: str = Query("BTC/USDT"),
    timeframe: str = Query("1h"),
    limit: int = Query(120, ge=20, le=200),
):
    if exchange not in EXCHANGES:
        raise HTTPException(400, "unsupported exchange")
    try:
        rows = None
        ticker = None
        if exchange == "binance":
            import urllib.parse
            import urllib.request

            interval = timeframe if timeframe in {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w"} else "1h"
            params = urllib.parse.urlencode({
                "symbol": symbol.replace("/", "").upper(),
                "interval": interval,
                "limit": limit,
            })
            with urllib.request.urlopen(
                "https://api.binance.com/api/v3/klines?" + params,
                timeout=7,
            ) as response:
                rows = json.loads(response.read().decode())
            try:
                with urllib.request.urlopen(
                    "https://api.binance.com/api/v3/ticker/24hr?" + urllib.parse.urlencode({"symbol": symbol.replace("/", "").upper()}),
                    timeout=5,
                ) as response:
                    t = json.loads(response.read().decode())
                    ticker = {
                        "last": float(t.get("lastPrice", 0)),
                        "bid": float(t.get("bidPrice", 0)),
                        "ask": float(t.get("askPrice", 0)),
                        "change": float(t.get("priceChangePercent", 0)),
                        "quote_volume": float(t.get("quoteVolume", 0)),
                        "timestamp": int(t.get("closeTime", 0)),
                    }
            except Exception:
                ticker = None

        if not rows:
            ex = make_exchange(exchange)
            ex.load_markets()
            if symbol not in ex.symbols:
                raise HTTPException(400, "symbol is not available on this exchange")
            rows = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if ex.has.get("fetchTicker"):
                try:
                    t = ex.fetch_ticker(symbol)
                    ticker = {
                        "last": t.get("last"),
                        "bid": t.get("bid"),
                        "ask": t.get("ask"),
                        "change": t.get("percentage"),
                        "quote_volume": t.get("quoteVolume"),
                        "timestamp": t.get("timestamp"),
                    }
                except Exception:
                    ticker = None

        if not rows:
            raise HTTPException(502, "no market data returned")
        result = compute_indicators(rows)
        return {"ok": True, "exchange": exchange, "symbol": symbol, "timeframe": timeframe, **result, "ticker": ticker}
    except HTTPException:
        raise
    except Exception:
        return safe_error("market data temporarily unavailable")


@app.get("/api/credentials")
def credentials_get(x_zerqen_dashboard_token: str | None = Header(default=None)):
    require_dashboard_token(x_zerqen_dashboard_token)
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT exchange_id, mode, updated_at FROM zerqen_exchange_credentials ORDER BY exchange_id"
            ).fetchall()
        return {
            "ok": True,
            "connections": [
                {"exchange_id": r[0], "mode": r[1], "updated_at": r[2].isoformat()} for r in rows
            ],
        }
    except Exception:
        return safe_error("connection service temporarily unavailable")


@app.post("/api/credentials")
def credentials_post(
    payload: dict[str, Any],
    x_zerqen_dashboard_token: str | None = Header(default=None),
):
    require_dashboard_token(x_zerqen_dashboard_token)
    exchange_id = payload.get("exchange_id")
    if exchange_id not in EXCHANGES:
        raise HTTPException(400, "unsupported exchange")
    action = payload.get("action")
    try:
        with get_db() as conn:
            if action == "delete":
                conn.execute("DELETE FROM zerqen_exchange_credentials WHERE exchange_id=%s", (exchange_id,))
                conn.commit()
                return {"ok": True, "deleted": exchange_id}

            if action != "save":
                raise HTTPException(400, "unsupported action")

            api_key = str(payload.get("api_key", "")).strip()
            api_secret = str(payload.get("api_secret", "")).strip()
            passphrase = str(payload.get("passphrase", "")).strip()
            mode = payload.get("mode", "testnet")
            if not api_key or not api_secret:
                raise HTTPException(400, "api key and secret are required")
            if mode not in {"testnet", "live"}:
                raise HTTPException(400, "invalid mode")

            nonce, ciphertext = encrypt_credentials(
                exchange_id,
                {"api_key": api_key, "api_secret": api_secret, "passphrase": passphrase},
            )
            conn.execute(
                """
                INSERT INTO zerqen_exchange_credentials
                    (exchange_id, mode, nonce, ciphertext, updated_at)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (exchange_id) DO UPDATE SET
                    mode=EXCLUDED.mode, nonce=EXCLUDED.nonce,
                    ciphertext=EXCLUDED.ciphertext, updated_at=EXCLUDED.updated_at
                """,
                (exchange_id, mode, nonce, ciphertext, datetime.now(timezone.utc)),
            )
            conn.commit()
            return {"ok": True, "saved": exchange_id, "encrypted": True}
    except HTTPException:
        raise
    except Exception:
        return safe_error("could not save connection")


@app.post("/api/exchange_test")
def exchange_test(
    payload: dict[str, Any],
    x_zerqen_dashboard_token: str | None = Header(default=None),
):
    require_dashboard_token(x_zerqen_dashboard_token)
    exchange_id = payload.get("exchange_id")
    if exchange_id not in EXCHANGES:
        raise HTTPException(400, "unsupported exchange")
    try:
        api_key = str(payload.get("api_key", "")).strip()
        api_secret = str(payload.get("api_secret", "")).strip()
        if not api_key or not api_secret:
            raise HTTPException(400, "api key and secret are required")
        ex = make_exchange(
            exchange_id,
            {
                "api_key": api_key,
                "api_secret": api_secret,
                "passphrase": str(payload.get("passphrase", "")).strip(),
            },
        )
        mode = payload.get("mode", "testnet")
        if mode == "testnet":
            if not ex.has.get("sandbox"):
                raise HTTPException(400, "testnet/sandbox is not supported by this exchange")
            ex.set_sandbox_mode(True)
        ex.load_markets()
        balance = ex.fetch_balance()
        return {
            "ok": True,
            "exchange": exchange_id,
            "mode": mode,
            "markets": len(ex.markets or {}),
            "authenticated": True,
            "balance_assets": len(balance.get("total", {})),
            "trading_test": False,
            "message": "read-only authentication and account access verified; no order was placed",
        }
    except HTTPException:
        raise
    except Exception:
        return safe_error("exchange authentication failed")


@app.get("/api/account")
def account(
    exchange: str,
    x_zerqen_dashboard_token: str | None = Header(default=None),
):
    require_dashboard_token(x_zerqen_dashboard_token)
    if exchange not in EXCHANGES:
        raise HTTPException(400, "unsupported exchange")
    try:
        mode, cred = load_credential(exchange)
        ex = make_exchange(exchange, cred)
        if mode == "testnet":
            if not ex.has.get("sandbox"):
                raise HTTPException(400, "saved connection does not support sandbox mode")
            ex.set_sandbox_mode(True)
        ex.load_markets()
        balance = ex.fetch_balance()
        total, free, used = balance.get("total") or {}, balance.get("free") or {}, balance.get("used") or {}

        assets = []
        for asset, value in total.items():
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if abs(number) > 1e-12:
                assets.append({"asset": asset, "total": number, "free": free.get(asset), "used": used.get(asset)})

        positions = []
        if ex.has.get("fetchPositions"):
            try:
                for p in ex.fetch_positions():
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
                pass

        trades = []
        if ex.has.get("fetchMyTrades"):
            try:
                for t in ex.fetch_my_trades(limit=25):
                    fee = t.get("fee") or {}
                    trades.append({
                        "id": str(t.get("id") or ""),
                        "timestamp": t.get("timestamp"),
                        "datetime": t.get("datetime"),
                        "symbol": t.get("symbol"),
                        "side": t.get("side"),
                        "price": t.get("price"),
                        "amount": t.get("amount"),
                        "cost": t.get("cost"),
                        "fee": fee.get("cost"),
                        "fee_currency": fee.get("currency"),
                    })
            except Exception:
                pass

        return {
            "ok": True,
            "exchange": exchange,
            "mode": mode,
            "assets": assets[:100],
            "positions": positions[:50],
            "trades": trades[:25],
            "server_time": datetime.now(timezone.utc).isoformat(),
        }
    except LookupError:
        raise HTTPException(404, "no saved connection")
    except HTTPException:
        raise
    except Exception:
        return safe_error("account data temporarily unavailable")
