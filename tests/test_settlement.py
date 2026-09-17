from datetime import datetime, timezone

from goji.models import MarketResult, Provenance, ResolvedOutcome
from goji.settlement import PlayerPropSettlementEvaluator, TeamSettlementEvaluator


def _market(odd_id="prop-1", score=2.0, supported=True):
    return MarketResult(odd_id, score, supported)


def _result(**overrides):
    data = {
        "provider_event_id": "evt-1",
        "sport": "MLB",
        "finalized": True,
        "home_team": "Cardinals",
        "away_team": "Giants",
        "home_score": 5.0,
        "away_score": 3.0,
        "market_results": {"prop-1": _market()},
        "players": {},
        "provenance": Provenance("SportsGameOdds", "evt-1", datetime(2026, 9, 16, tzinfo=timezone.utc)),
        "raw_reference": {},
    }
    data.update(overrides)
    return ResolvedOutcome(**data)


def test_team_selection_wins_from_final_score():
    decision = TeamSettlementEvaluator().evaluate(
        {"selection": "Cardinals"},
        _result(home_team="Cardinals", away_team="Giants", home_score=5, away_score=3),
    )
    assert decision.outcome == "WIN"
    assert decision.evaluator_version == "team-winner-v1"


def test_team_selection_loses_from_final_score():
    decision = TeamSettlementEvaluator().evaluate(
        {"selection": "Giants"},
        _result(home_team="Cardinals", away_team="Giants", home_score=5, away_score=3),
    )
    assert decision.outcome == "LOSS"


def test_final_tie_is_review_not_assumed_push():
    decision = TeamSettlementEvaluator().evaluate(
        {"selection": "Cardinals"},
        _result(home_score=3, away_score=3),
    )
    assert decision.outcome == "REVIEW_REQUIRED"


def test_team_selection_must_match_result_identity():
    decision = TeamSettlementEvaluator().evaluate({"selection": "Unknown"}, _result())
    assert decision.outcome == "REVIEW_REQUIRED"


def test_prop_over_uses_exact_provider_market_score():
    decision = PlayerPropSettlementEvaluator().evaluate(
        {"inputs": {"line": 1.5, "side": "OVER", "provider_odd_id": "prop-1"}},
        _result(market_results={"prop-1": _market("prop-1", 2.0, True)}),
    )
    assert decision.outcome == "WIN"
    assert decision.evaluator_version == "player-prop-v1"


def test_prop_under_loses_when_score_above_line():
    decision = PlayerPropSettlementEvaluator().evaluate(
        {"inputs": {"line": 1.5, "side": "UNDER", "provider_odd_id": "prop-1"}},
        _result(market_results={"prop-1": _market("prop-1", 2.0, True)}),
    )
    assert decision.outcome == "LOSS"


def test_prop_equal_line_is_push():
    decision = PlayerPropSettlementEvaluator().evaluate(
        {"inputs": {"line": 2.0, "side": "OVER", "provider_odd_id": "prop-1"}},
        _result(market_results={"prop-1": _market("prop-1", 2.0, True)}),
    )
    assert decision.outcome == "PUSH"


def test_prop_missing_score_requires_review():
    decision = PlayerPropSettlementEvaluator().evaluate(
        {"inputs": {"line": 2.0, "side": "OVER", "provider_odd_id": "prop-1"}},
        _result(market_results={}),
    )
    assert decision.outcome == "REVIEW_REQUIRED"
