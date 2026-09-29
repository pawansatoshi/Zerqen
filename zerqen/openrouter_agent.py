from __future__ import annotations

import json, os, time, urllib.error, urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

OPENROUTER_BASE = 'https://openrouter.ai/api/v1'
FREE_ROUTER = 'openrouter/free'

@dataclass(frozen=True)
class FreeModel:
    model_id: str
    prompt_price: Decimal
    completion_price: Decimal
    context_length: int

class FreeOnlyViolation(RuntimeError):
    pass

class FreeModelRegistry:
    def __init__(self):
        self.refresh_seconds = max(60, int(os.getenv('ZERQEN_AI_MODEL_REFRESH_SECONDS','300')))
        self.max_attempts = max(1, min(5, int(os.getenv('ZERQEN_AI_MAX_FALLBACKS','3'))))
        self._models = []
        self._last_refresh = 0.0
        self._cooldown = {}

    @staticmethod
    def _price(value: Any):
        try:
            return Decimal(str(value))
        except Exception:
            return None

    @classmethod
    def _is_free(cls, model):
        p = model.get('pricing') or {}
        return cls._price(p.get('prompt')) == Decimal('0') and cls._price(p.get('completion')) == Decimal('0')

    def refresh(self, force=False):
        now = time.monotonic()
        if not force and self._models and now - self._last_refresh < self.refresh_seconds:
            return self._models
        payload = _http_json('GET', OPENROUTER_BASE + '/models')
        models = []
        for raw in payload.get('data', []):
            if not isinstance(raw, dict) or not self._is_free(raw):
                continue
            mid = str(raw.get('id') or '').strip()
            if not mid:
                continue
            p = raw.get('pricing') or {}
            models.append(FreeModel(mid, self._price(p.get('prompt')) or Decimal('1'), self._price(p.get('completion')) or Decimal('1'), int(raw.get('context_length') or 0)))
        if not any(m.model_id == FREE_ROUTER for m in models):
            models.append(FreeModel(FREE_ROUTER, Decimal('0'), Decimal('0'), 200000))
        self._models = sorted(models, key=lambda m: (m.model_id == FREE_ROUTER, -m.context_length, m.model_id))
        self._last_refresh = now
        return self._models

    def active_models(self):
        now = time.monotonic()
        return [m for m in self.refresh() if self._cooldown.get(m.model_id, 0) <= now]

    def mark_failed(self, model_id, seconds=300):
        self._cooldown[model_id] = time.monotonic() + seconds

    def snapshot(self):
        models = self.refresh(); now = time.monotonic()
        return {'enabled': bool(os.getenv('OPENROUTER_API_KEY')), 'free_model_count': len([m for m in models if m.model_id != FREE_ROUTER]), 'models': [{'id':m.model_id,'prompt_price':str(m.prompt_price),'completion_price':str(m.completion_price),'context_length':m.context_length,'eligible':m.prompt_price==0 and m.completion_price==0,'cooldown':self._cooldown.get(m.model_id,0)>now} for m in models], 'refresh_seconds':self.refresh_seconds, 'max_fallback_attempts':self.max_attempts}

REGISTRY = FreeModelRegistry()

def _http_json(method, url, payload=None):
    body = json.dumps(payload, separators=(',', ':')).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={'Accept':'application/json','Content-Type':'application/json','Authorization':f"Bearer {os.environ.get('OPENROUTER_API_KEY','')}",'HTTP-Referer':os.environ.get('OPENROUTER_HTTP_REFERER','https://zerqen.local'),'X-Title':'Zerqen Free-Only AI Agent','User-Agent':'Zerqen-FreeOnly-Agent/1.0'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode())

def _extract_text(payload):
    choices = payload.get('choices') or []
    if not choices:
        raise ValueError('OpenRouter returned no choices')
    content = (choices[0].get('message') or {}).get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(str(p.get('text', '')) for p in content if isinstance(p, dict))
    raise ValueError('OpenRouter returned no text content')

def _parse_decision(text):
    cleaned = text.strip().strip('`')
    if cleaned.startswith('json'):
        cleaned = cleaned[4:].strip()
    start, end = cleaned.find('{'), cleaned.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('AI response was not JSON')
    result = json.loads(cleaned[start:end+1])
    decision = str(result.get('decision','HOLD')).upper()
    if decision not in {'BUY','SELL','HOLD'}:
        decision = 'HOLD'
    confidence = max(0.0, min(1.0, float(result.get('confidence',0))))
    flags = result.get('risk_flags', [])
    return {'decision':decision,'confidence':confidence,'reason':str(result.get('reason',''))[:1000],'risk_flags':flags if isinstance(flags,list) else [],'invalidation':str(result.get('invalidation',''))[:500]}

def evaluate_setup(context):
    if not os.getenv('OPENROUTER_API_KEY'):
        return {
            'enabled': False, 'decision': 'HOLD', 'confidence': 0.0,
            'reason': 'OPENROUTER_API_KEY is not configured', 'model': None, 'attempts': [],
        }
    system = 'You are Zerqen paper-trading research agent. Use only supplied facts. Return ONLY JSON with decision BUY/SELL/HOLD, confidence 0..1, reason, risk_flags array, invalidation. Hard deterministic risk controls are authoritative.'
    user = json.dumps(context, separators=(',',':'), default=str); attempts=[]
    for model in REGISTRY.active_models()[:REGISTRY.max_attempts]:
        if model.prompt_price != 0 or model.completion_price != 0:
            raise FreeOnlyViolation(f'paid model blocked: {model.model_id}')
        try:
            response = _http_json('POST', OPENROUTER_BASE + '/chat/completions', {'model':model.model_id,'messages':[{'role':'system','content':system},{'role':'user','content':user}],'temperature':0,'max_tokens':300})
            cost = (response.get('usage') or {}).get('cost')
            if cost is not None and Decimal(str(cost)) != 0:
                raise FreeOnlyViolation(f'non-zero inference cost from {model.model_id}')
            parsed = _parse_decision(_extract_text(response)); attempts.append({'model':model.model_id,'ok':True})
            return {'enabled':True,**parsed,'model':model.model_id,'attempts':attempts}
        except FreeOnlyViolation:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            REGISTRY.mark_failed(model.model_id); attempts.append({'model':model.model_id,'ok':False,'error':type(exc).__name__})
    return {'enabled':True,'decision':'HOLD','confidence':0.0,'reason':'No healthy verified-free OpenRouter model was available','risk_flags':['AI_FALLBACK_EXHAUSTED'],'invalidation':'','model':None,'attempts':attempts}

def health():
    if not os.getenv('OPENROUTER_API_KEY'):
        return {
            'ok': True, 'enabled': False, 'free_only': True,
            'reason': 'OPENROUTER_API_KEY not configured',
        }
    try:
        models = REGISTRY.refresh(force=True)
        return {'ok':True,'enabled':True,'free_only':True,'verified_free_models':len(models),'models':[m.model_id for m in models]}
    except Exception as exc:  # noqa: BLE001
        return {
            'ok': False, 'enabled': True, 'free_only': True,
            'error': str(exc)[:500],
        }
