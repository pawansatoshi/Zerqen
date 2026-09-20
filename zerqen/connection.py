from __future__ import annotations
import os
from dataclasses import dataclass
from .exchanges import ExchangeId, get_exchange

@dataclass(frozen=True)
class ExchangeCredentials:
    exchange_id: ExchangeId
    values: dict[str, str]

def load_credentials(exchange_id: str | ExchangeId, *, environ: dict[str, str] | None = None) -> ExchangeCredentials:
    env = os.environ if environ is None else environ
    profile = get_exchange(exchange_id)
    missing = [key for key in profile.credential_env if not env.get(key)]
    if missing:
        raise ValueError(f"missing credentials for {profile.display_name}: {', '.join(missing)}")
    return ExchangeCredentials(profile.exchange_id, {key: env[key] for key in profile.credential_env})

def connection_options() -> tuple[dict[str, object], ...]:
    return tuple({
        "id": profile.exchange_id.value,
        "name": profile.display_name,
        "adapter": profile.adapter,
        "credential_env": profile.credential_env,
        "spot": profile.supports_spot,
        "derivatives": profile.supports_derivatives,
    } for profile in EXCHANGE_PROFILES.values())
