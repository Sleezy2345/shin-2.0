from datetime import datetime, timezone

from goji.models import PregameCandidate, PreparedSlate, Provenance, ValidationState


def test_pregame_candidate_preserves_operational_evidence():
    observed_at = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    provenance = (Provenance(provider="SportsGameOdds", source_id="evt-1", observed_at=observed_at),)

    candidate = PregameCandidate(
        prediction_id="pred-1",
        sport="MLB",
        game_id="evt-1",
        prediction_type="TEAM",
        selection="Cardinals",
        market_key="moneyline",
        independent_group_key="MLB:evt-1:TEAM",
        inputs={"home_team": "Cardinals", "away_team": "Giants"},
        features={"baseline_probability": 0.58},
        provenance=provenance,
        context={"venue": "Busch Stadium"},
    )

    assert candidate.independent_group_key == "MLB:evt-1:TEAM"
    assert candidate.provenance == provenance
    assert candidate.inputs["home_team"] == "Cardinals"
    assert candidate.features["baseline_probability"] == 0.58
    assert candidate.context["venue"] == "Busch Stadium"


def test_validation_state_serializes_for_genome():
    state = ValidationState(decision="PASS_WITH_CAUTION", reasons=("evidence aging",))
    assert state.as_dict() == {"decision": "PASS_WITH_CAUTION", "reasons": ["evidence aging"]}


def test_prepared_slate_keeps_predictions_and_blocked_separate():
    prepared = PreparedSlate(
        slate_id="2026-09-16-MLB",
        predictions=({"prediction_id": "pred-1"},),
        blocked=({"blocked_id": "blocked-1"},),
    )

    assert prepared.predictions == ({"prediction_id": "pred-1"},)
    assert prepared.blocked == ({"blocked_id": "blocked-1"},)
