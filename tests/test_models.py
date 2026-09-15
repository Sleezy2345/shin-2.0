from datetime import datetime, timezone

from goji.models import NormalizedEvent, PredictionDecision, PredictionInput, Provenance


def test_normalized_event_preserves_provider_provenance():
    source_time = datetime(2026, 9, 15, 17, 0, tzinfo=timezone.utc)
    event = NormalizedEvent(
        event_id="evt-1",
        league="MLB",
        home_team="Cardinals",
        away_team="Giants",
        starts_at=source_time,
        provenance=Provenance(provider="SportsGameOdds", source_id="evt-1", observed_at=source_time),
    )
    assert event.provenance.provider == "SportsGameOdds"
    assert event.provenance.source_id == "evt-1"


def test_prediction_decision_keeps_model_probability_separate_from_market_probability():
    decision = PredictionDecision(
        prediction_id="pred-1",
        selection="Cardinals",
        model_probability=0.61,
        market_implied_probability=0.55,
        model_status="COLD_START",
        roar_action="NO_ROAR",
        reason="baseline only",
    )
    assert decision.model_probability == 0.61
    assert decision.market_implied_probability == 0.55
