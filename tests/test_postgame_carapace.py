from datetime import datetime, timezone

from goji.models import MarketResult, Provenance, ResolvedOutcome
from goji.postgame_carapace import PostgameCarapace


def _result(**overrides):
    data = {
        "provider_event_id": "evt-1",
        "sport": "MLB",
        "finalized": True,
        "home_team": "Cardinals",
        "away_team": "Giants",
        "home_score": 5.0,
        "away_score": 3.0,
        "market_results": {"prop-1": MarketResult("prop-1", 2.0, True)},
        "players": {},
        "provenance": Provenance("SportsGameOdds", "evt-1", datetime(2026, 9, 16, tzinfo=timezone.utc)),
        "raw_reference": {},
    }
    data.update(overrides)
    return ResolvedOutcome(**data)


def test_finalized_team_result_passes():
    frozen = {
        "sport": "MLB",
        "game_id": "internal-game-1",
        "prediction_type": "TEAM",
        "inputs": {"provider_event_id": "evt-1"},
    }
    assert PostgameCarapace().evaluate(_result(), frozen).decision == "PASS"


def test_non_final_result_blocks():
    frozen = {"sport": "MLB", "prediction_type": "TEAM", "inputs": {"provider_event_id": "evt-1"}}
    state = PostgameCarapace().evaluate(_result(finalized=False), frozen)
    assert state.decision == "BLOCKED"


def test_provider_event_mismatch_requires_review():
    frozen = {"sport": "MLB", "prediction_type": "TEAM", "inputs": {"provider_event_id": "evt-other"}}
    state = PostgameCarapace().evaluate(_result(), frozen)
    assert state.decision == "REVIEW_REQUIRED"


def test_missing_team_score_requires_review():
    frozen = {"sport": "MLB", "prediction_type": "TEAM", "inputs": {"provider_event_id": "evt-1"}}
    state = PostgameCarapace().evaluate(_result(home_score=None), frozen)
    assert state.decision == "REVIEW_REQUIRED"


def test_player_prop_without_exact_supported_market_score_requires_review():
    frozen = {
        "sport": "MLB",
        "prediction_type": "PLAYER_PROP",
        "inputs": {"provider_event_id": "evt-1", "provider_odd_id": "prop-1"},
    }
    state = PostgameCarapace().evaluate(
        _result(market_results={"prop-1": MarketResult("prop-1", None, False)}),
        frozen,
    )
    assert state.decision == "REVIEW_REQUIRED"
