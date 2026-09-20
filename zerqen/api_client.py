from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

@dataclass(frozen=True)
class ApiCredentials:
    api_key: str
    api_secret: str
    passphrase: str | None = None

class ExchangeHttpError(RuntimeError):
    pass

class SignedHttpClient:
    """Minimal stdlib HTTP transport. Network calls are opt-in at method call time."""
    def __init__(self, base_url: str, credentials: ApiCredentials, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.timeout = timeout

    def request(self, method: str, path: str, *, params=None, body=None, headers=None):
        query = urlencode(params or {})
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        payload = json.dumps(body or {}, separators=(",", ":")).encode()
        request = Request(url, data=payload if method != "GET" else None, method=method.upper())
        request.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode()
        except Exception as exc:
            raise ExchangeHttpError(str(exc)) from exc
        return json.loads(raw) if raw else {}

def hmac_sha256_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

def hmac_sha512_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha512).hexdigest()

def hmac_sha256_base64(secret: str, message: str) -> str:
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()

def delta_signature(secret: str, method: str, path: str, timestamp: str, body: str = "") -> str:
    message = method.upper() + timestamp + path + body
    return hmac_sha256_hex(secret, message)

def okx_signature(secret: str, timestamp: str, method: str, request_path: str, body: str = "") -> str:
    message = timestamp + method.upper() + request_path + body
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()

def bitget_signature(secret: str, timestamp: str, method: str, request_path: str, query: str = "", body: str = "") -> str:
    message = timestamp + method.upper() + request_path
    if query:
        message += "?" + query
    message += body
    return hmac_sha256_base64(secret, message)

def gate_signature(secret: str, method: str, path: str, query: str, body: str, timestamp: str) -> str:
    body_hash = hashlib.sha512(body.encode()).hexdigest()
    message = "\n".join([method.upper(), path, query, body_hash, timestamp])
    return hmac_sha512_hex(secret, message)

def wazirx_signature(secret: str, params: dict[str, object]) -> str:
    return hmac_sha256_hex(secret, urlencode(params))

def epoch_ms() -> int:
    return int(time.time() * 1000)
