from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


REPORT_TTL_SECONDS = int(os.getenv("ZERQEN_AI_REPORT_TTL_SECONDS", "900"))


@dataclass(frozen=True)
class AIRuntimeState:
    mode: str
    degraded_until: float | None
    last_ok_at: float | None
    last_error: str | None
    last_model: str | None
    last_confidence: float | None
    report_hash: str | None


@dataclass
class MarketIntelligenceReport:
    symbol: str
    exchange: str
    generated_at: str
    price: float
    timeframes: dict[str, Any]
    market_structure: dict[str, Any]
    derivatives: dict[str, Any]
    options: dict[str, Any]
    setup_candidates: list[dict[str, Any]]
    portfolio: dict[str, Any]
    risk: dict[str, Any]
    data_quality: dict[str, Any]
    warnings: list[str]
    report_hash: str = ""

    def finalize(self) -> "MarketIntelligenceReport":
        payload = asdict(self)
        payload.pop("report_hash", None)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        self.report_hash = hashlib.sha256(canonical.encode()).hexdigest()
        return self


_REPORT_CACHE: dict[str, tuple[float, MarketIntelligenceReport]] = {}


def _json_get(url: str, timeout: float = 6.0) -> dict[str, Any] | list[Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "Zerqen/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    value = sum(values[:period]) / period
    for item in values[period:]:
        value = item * k + value * (1.0 - k)
    return value


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for i in range(len(values) - period, len(values)):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def _atr(rows: list[list[Any]], period: int = 14) -> float | None:
    if len(rows) <= period:
        return None
    trs: list[float] = []
    for i, row in enumerate(rows):
        high, low = float(row[2]), float(row[3])
        previous = float(rows[i - 1][4]) if i else float(row[4])
        trs.append(max(high - low, abs(high - previous), abs(low - previous)))
    return sum(trs[-period:]) / period


def _macd(values: list[float]) -> dict[str, float | None]:
    fast = _ema(values, 12)
    slow = _ema(values, 26)
    if fast is None or slow is None:
        return {"macd": None, "signal": None, "histogram": None}
    macd_series: list[float] = []
    for i in range(len(values)):
        f = _ema(values[: i + 1], 12)
        s = _ema(values[: i + 1], 26)
        if f is not None and s is not None:
            macd_series.append(f - s)
    signal = _ema(macd_series, 9)
    macd_value = macd_series[-1] if macd_series else None
    return {
        "macd": macd_value,
        "signal": signal,
        "histogram": None if macd_value is None or signal is None else macd_value - signal,
    }


def _adx(rows: list[list[Any]], period: int = 14) -> float | None:
    if len(rows) < period * 2:
        return None
    trs: list[float] = []
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    for i in range(1, len(rows)):
        high, low = float(rows[i][2]), float(rows[i][3])
        prev_high, prev_low, prev_close = float(rows[i - 1][2]), float(rows[i - 1][3]), float(rows[i - 1][4])
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        up = high - prev_high
        down = prev_low - low
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
    dx: list[float] = []
    for i in range(period - 1, len(trs)):
        tr = sum(trs[i - period + 1 : i + 1])
        if tr <= 0:
            continue
        p = sum(plus_dm[i - period + 1 : i + 1]) / tr
        m = sum(minus_dm[i - period + 1 : i + 1]) / tr
        dx.append(100.0 * abs(p - m) / max(p + m, 1e-12))
    return sum(dx[-period:]) / len(dx[-period:]) if dx else None


def _timeframe_report(rows: list[list[Any]]) -> dict[str, Any]:
    closes = [float(r[4]) for r in rows]
    highs = [float(r[2]) for r in rows]
    lows = [float(r[3]) for r in rows]
    volumes = [float(r[5]) for r in rows]
    price = closes[-1]
    atr = _atr(rows)
    atr_pct = None if not atr or price <= 0 else atr / price
    mean_volume = sum(volumes[-21:-1]) / max(len(volumes[-21:-1]), 1)
    max_bar_pct = max(
        (abs(float(r[2]) - float(r[3])) / max(float(r[4]), 1e-12) for r in rows[-20:]),
        default=0.0,
    )
    ema9, ema21, ema50, ema200 = (
        _ema(closes, 9),
        _ema(closes, 21),
        _ema(closes, 50),
        _ema(closes, 200),
    )
    momentum = None if len(closes) < 11 else closes[-1] / closes[-11] - 1.0
    bb_mid = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
    bb_std = (
        (sum((x - bb_mid) ** 2 for x in closes[-20:]) / 20) ** 0.5
        if bb_mid is not None
        else None
    )
    bb_upper = None if bb_mid is None or bb_std is None else bb_mid + 2 * bb_std
    bb_lower = None if bb_mid is None or bb_std is None else bb_mid - 2 * bb_std
    bandwidth = None if bb_mid in (None, 0) or bb_upper is None else (bb_upper - bb_lower) / bb_mid
    return {
        "bars": len(rows),
        "close": price,
        "ema9": ema9,
        "ema21": ema21,
        "ema50": ema50,
        "ema200": ema200,
        "rsi14": _rsi(closes),
        "atr14": atr,
        "atr_pct": atr_pct,
        "adx14": _adx(rows),
        "macd": _macd(closes),
        "momentum_10": momentum,
        "volume_ratio": None if mean_volume <= 0 else volumes[-1] / mean_volume,
        "bollinger": {
            "mid": bb_mid,
            "upper": bb_upper,
            "lower": bb_lower,
            "bandwidth": bandwidth,
        },
        "support": min(lows[-30:]) if lows else None,
        "resistance": max(highs[-30:]) if highs else None,
        "max_bar_pct": max_bar_pct,
    }


def _fetch_timeframe(exchange: str, symbol: str, timeframe: str) -> tuple[list[list[Any]], dict[str, Any]]:
    from api.market import public_market_probe

    result = public_market_probe(exchange, symbol, timeframe, 240)
    if result.get("connectivity_status") not in {"WORKING", "DEGRADED"}:
        raise RuntimeError(result.get("error_type") or "market data unavailable")
    closes = result.get("closes") or []
    if not closes:
        raise RuntimeError("no candles returned")
    rows = [
        [result["times"][i], result["opens"][i], result["highs"][i], result["lows"][i],
         result["closes"][i], result["volumes"][i]]
        for i in range(len(closes))
    ]
    return rows, result


def _derivatives(symbol: str) -> dict[str, Any]:
    pair = symbol.replace("/", "").upper()
    out: dict[str, Any] = {"status": "UNAVAILABLE", "symbol": pair}
    try:
        ticker = _json_get(
            "https://fapi.binance.com/fapi/v1/premiumIndex?" + urllib.parse.urlencode({"symbol": pair})
        )
        oi = _json_get(
            "https://fapi.binance.com/fapi/v1/openInterest?" + urllib.parse.urlencode({"symbol": pair})
        )
        out.update(
            {
                "status": "AVAILABLE",
                "mark_price": ticker.get("markPrice"),
                "index_price": ticker.get("indexPrice"),
                "funding_rate": ticker.get("lastFundingRate"),
                "next_funding_time": ticker.get("nextFundingTime"),
                "open_interest": oi.get("openInterest"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        out["warning"] = str(exc)[:180]
    return out


def _options(symbol: str) -> dict[str, Any]:
    pair = symbol.replace("/", "").upper()
    out: dict[str, Any] = {"status": "UNAVAILABLE", "underlying": pair}
    try:
        info = _json_get("https://eapi.binance.com/eapi/v1/exchangeInfo")
        symbols = info.get("optionSymbols") or []
        matching = [
            x for x in symbols
            if str(x.get("underlying") or "").replace("_", "").upper() == pair
        ]
        expiries = sorted({x.get("expiryDate") for x in matching if x.get("expiryDate")})
        out.update(
            {
                "status": "AVAILABLE",
                "contracts": len(matching),
                "nearest_expiry": expiries[0] if expiries else None,
                "expiry_count": len(expiries),
            }
        )
    except Exception as exc:  # noqa: BLE001
        out["warning"] = str(exc)[:180]
    return out


def _market_structure(tf: dict[str, Any]) -> dict[str, Any]:
    close = tf.get("close")
    e9, e21, e50, e200 = tf.get("ema9"), tf.get("ema21"), tf.get("ema50"), tf.get("ema200")
    if close is None or e9 is None or e21 is None:
        return {"regime": "INSUFFICIENT_DATA", "bias": "NEUTRAL"}
    if e9 > e21 and (e50 is None or e21 > e50):
        regime = "TREND_UP"
        bias = "LONG"
    elif e9 < e21 and (e50 is None or e21 < e50):
        regime = "TREND_DOWN"
        bias = "SHORT"
    else:
        regime = "RANGE"
        bias = "NEUTRAL"
    return {
        "regime": regime,
        "bias": bias,
        "price_above_ema200": None if e200 is None else close > e200,
        "ema_alignment": {
            "9_21": None if e9 is None or e21 is None else e9 > e21,
            "21_50": None if e21 is None or e50 is None else e21 > e50,
            "50_200": None if e50 is None or e200 is None else e50 > e200,
        },
    }


def _setups(tfs: dict[str, Any], risk: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for direction, key in (("BUY", "LONG"), ("SELL", "SHORT")):
        one = tfs.get("1h", {})
        four = tfs.get("4h", {})
        rsi = one.get("rsi14")
        momentum = one.get("momentum_10")
        trend_ok = (
            (direction == "BUY" and four.get("ema9") and four.get("ema21") and four["ema9"] > four["ema21"])
            or (direction == "SELL" and four.get("ema9") and four.get("ema21") and four["ema9"] < four["ema21"])
        )
        momentum_ok = momentum is not None and ((direction == "BUY" and momentum > 0) or (direction == "SELL" and momentum < 0))
        rsi_ok = rsi is not None and ((direction == "BUY" and 45 <= rsi <= 70) or (direction == "SELL" and 30 <= rsi <= 55))
        if trend_ok and momentum_ok and rsi_ok and risk.get("volatility_ok", False):
            out.append(
                {
                    "side": direction,
                    "name": "multi_timeframe_trend",
                    "conditions": ["4h trend alignment", "1h momentum", "RSI regime", "volatility gate"],
                    "invalidation": "1h/4h trend structure breaks or volatility gate fails",
                    "risk_reward": risk.get("min_risk_reward", 2.0),
                }
            )
    return out


def build_report(
    exchange: str,
    symbol: str,
    portfolio: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    force: bool = False,
) -> MarketIntelligenceReport:
    key = f"{exchange}:{symbol.upper()}"
    cached = _REPORT_CACHE.get(key)
    if cached and not force and time.time() - cached[0] < REPORT_TTL_SECONDS:
        return cached[1]

    tfs: dict[str, Any] = {}
    warnings: list[str] = []
    sources: dict[str, str] = {}
    latest_price: float | None = None
    for timeframe in ("1h", "4h", "1d"):
        try:
            rows, source = _fetch_timeframe(exchange, symbol, timeframe)
            tfs[timeframe] = _timeframe_report(rows)
            latest_price = latest_price or float(tfs[timeframe]["close"])
            sources[timeframe] = str(source.get("connectivity_status", "UNKNOWN"))
        except Exception as exc:  # noqa: BLE001
            tfs[timeframe] = {"status": "UNAVAILABLE", "error": str(exc)[:180]}
            warnings.append(f"{timeframe}: data unavailable")

    if latest_price is None:
        raise RuntimeError("market intelligence requires at least one valid timeframe")

    one_hour = tfs.get("1h", {})
    computed_risk = dict(risk or {})
    atr_pct = one_hour.get("atr_pct")
    max_bar_pct = one_hour.get("max_bar_pct")
    computed_risk.setdefault("volatility_ok", atr_pct is not None and max_bar_pct is not None and atr_pct <= 0.05 and max_bar_pct <= 0.08)
    computed_risk.setdefault("min_risk_reward", 2.0)

    derivatives = _derivatives(symbol)
    options = _options(symbol)
    if derivatives.get("status") != "AVAILABLE":
        warnings.append("futures derivatives context unavailable")
    if options.get("status") != "AVAILABLE":
        warnings.append("options expiry context unavailable")

    structure = _market_structure(one_hour)
    quality_score = sum(1 for value in tfs.values() if value.get("close") is not None) / 3.0
    quality = {
        "score": round(quality_score, 3),
        "timeframes_available": [k for k, v in tfs.items() if v.get("close") is not None],
        "sources": sources,
        "warnings": warnings,
    }
    report = MarketIntelligenceReport(
        symbol=symbol,
        exchange=exchange,
        generated_at=datetime.now(timezone.utc).isoformat(),
        price=latest_price,
        timeframes=tfs,
        market_structure=structure,
        derivatives=derivatives,
        options=options,
        setup_candidates=_setups(tfs, computed_risk),
        portfolio=portfolio or {},
        risk=computed_risk,
        data_quality=quality,
        warnings=warnings,
    ).finalize()
    _REPORT_CACHE[key] = (time.time(), report)
    return report


def report_for_ai(report: MarketIntelligenceReport) -> dict[str, Any]:
    payload = asdict(report)
    payload["schema_version"] = "1.0"
    payload["ai_instruction"] = (
        "Synthesize only supplied evidence. Do not invent missing values. "
        "Do not override hard risk gates. Return HOLD when evidence is insufficient."
    )
    return payload


def runtime_state() -> AIRuntimeState:
    degraded_until = float(os.getenv("ZERQEN_AI_DEGRADED_UNTIL", "0") or 0)
    return AIRuntimeState(
        mode=os.getenv("ZERQEN_AI_MODE", "auto").lower(),
        degraded_until=degraded_until or None,
        last_ok_at=None,
        last_error=None,
        last_model=None,
        last_confidence=None,
        report_hash=None,
    )


def should_use_safe_mode() -> bool:
    if os.getenv("ZERQEN_AI_SAFE_MODE", "true").lower() not in {"1", "true", "yes", "on"}:
        return False
    until = float(os.getenv("ZERQEN_AI_DEGRADED_UNTIL", "0") or 0)
    return until > time.time()


def enter_safe_mode(reason: str) -> AIRuntimeState:
    seconds = int(os.getenv("ZERQEN_AI_SAFE_RETRY_SECONDS", "1800"))
    os.environ["ZERQEN_AI_DEGRADED_UNTIL"] = str(time.time() + seconds)
    os.environ["ZERQEN_AI_LAST_ERROR"] = reason[:300]
    return runtime_state()


def exit_safe_mode() -> AIRuntimeState:
    os.environ.pop("ZERQEN_AI_DEGRADED_UNTIL", None)
    os.environ["ZERQEN_AI_LAST_ERROR"] = ""
    return runtime_state()


def runtime_payload() -> dict[str, Any]:
    state = runtime_state()
    return {
        **asdict(state),
        "safe_mode_active": should_use_safe_mode(),
        "safe_mode_enabled": os.getenv("ZERQEN_AI_SAFE_MODE", "true").lower() in {"1", "true", "yes", "on"},
        "real_ai_required": os.getenv("ZERQEN_REAL_AI_REQUIRED", "true").lower() in {"1", "true", "yes", "on"},
    }
