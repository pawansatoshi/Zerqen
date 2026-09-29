from zerqen.strategy_registry import StrategyStatus, eligible_strategies


def test_unvalidated_strategies_never_enter_runtime():
    assert eligible_strategies("trend_up") == ()
    assert eligible_strategies("range") == ()


def test_only_validated_and_regime_compatible_strategies_are_eligible():
    from zerqen.strategy_registry import StrategyEvidence

    evidence = (
        StrategyEvidence("trend", StrategyStatus.VALIDATED, ("trend_up",)),
        StrategyEvidence("mean_reversion", StrategyStatus.VALIDATED, ("range",)),
        StrategyEvidence("disabled", StrategyStatus.DISABLED, ("trend_up",)),
    )
    assert [x.strategy_id for x in eligible_strategies("trend_up", evidence)] == ["trend"]
