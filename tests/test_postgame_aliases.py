from datetime import datetime, timezone

from goji.models import MarketResult, Provenance, ResolvedOutcome
from goji.results import parse_sgo_result
from goji.settlement import PlayerPropSettlementEvaluator


def _result(score=2.0):
    return ResolvedOutcome(
        provider_event_id="evt-1",
        sport="MLB",
        finalized=True,
        home_team="Cardinals",
        away_team="Giants",
        home_score=5.0,
        away_score=3.0,
        market_results={"prop-1": MarketResult("prop-1", score, True)},
        players={},
        provenance=Provenance("SportsGameOdds", "evt-1", datetime(2026, 9, 16, tzinfo=timezone.utc)),
        raw_reference={},
    )


def test_higher_is_canonical_over_for_v02_prop_compatibility():
    decision = PlayerPropSettlementEvaluator().evaluate(
        {"inputs": {"line": 1.5, "side": "HIGHER", "provider_odd_id": "prop-1"}},
        _result(2.0),
    )
    assert decision.outcome == "WIN"
    assert decision.grading_inputs["side"] == "OVER"


def test_lower_is_canonical_under_for_v02_prop_compatibility():
    decision = PlayerPropSettlementEvaluator().evaluate(
        {"inputs": {"line": 2.5, "side": "LOWER", "provider_odd_id": "prop-1"}},
        _result(2.0),
    )
    assert decision.outcome == "WIN"
    assert decision.grading_inputs["side"] == "UNDER"


def test_sgo_ncaaf_normalizes_to_goji_cfb():
    row = {
        "eventID": "evt-cfb",
        "leagueID": "NCAAF",
        "teams": {
            "home": {"names": {"long": "Home"}},
            "away": {"names": {"long": "Away"}},
        },
        "status": {"finalized": True},
        "scores": {"home": 28, "away": 21},
    }
    result = parse_sgo_result(row)
    assert result.sport == "CFB"
