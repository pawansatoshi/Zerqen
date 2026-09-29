from decimal import Decimal

import zerqen.openrouter_agent as agent


def test_registry_admits_only_zero_priced_models(monkeypatch):
    monkeypatch.setattr(agent, '_http_json', lambda method, url, payload=None: {'data': [
        {'id':'free-a','pricing':{'prompt':'0','completion':'0'},'context_length':1000},
        {'id':'paid-a','pricing':{'prompt':'0.1','completion':'0.2'},'context_length':1000},
        {'id':'free-b','pricing':{'prompt':'0','completion':'0'},'context_length':2000},
    ]})
    registry = agent.FreeModelRegistry()
    models = registry.refresh(force=True)
    ids = {m.model_id for m in models}
    assert 'free-a' in ids and 'free-b' in ids
    assert 'paid-a' not in ids
    assert all(m.prompt_price == Decimal(0) and m.completion_price == Decimal(0) for m in models)


def test_paid_model_can_never_be_called(monkeypatch):
    registry = agent.FreeModelRegistry()
    registry._models = [agent.FreeModel('paid-a', Decimal(1), Decimal(1), 1000)]
    monkeypatch.setattr(agent, 'REGISTRY', registry)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test')
    try:
        agent.evaluate_setup({'signal':'BUY'})
    except agent.FreeOnlyViolation:
        pass
    else:
        raise AssertionError('paid model was not blocked')


def test_new_free_model_is_discovered(monkeypatch):
    payload = {'data': [{'id':'new-free','pricing':{'prompt':'0','completion':'0'},'context_length':4000}]}
    monkeypatch.setattr(agent, '_http_json', lambda method, url, payload=None: {'data': [{'id':'new-free','pricing':{'prompt':'0','completion':'0'},'context_length':4000}]})
    registry = agent.FreeModelRegistry()
    models = registry.refresh(force=True)
    assert any(m.model_id == 'new-free' for m in models)
