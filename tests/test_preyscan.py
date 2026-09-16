import pytest

from goji.models import PregameCandidate
from goji.preyscan import PreyScan


def _prop(**input_overrides):
    inputs = {
        "player": "Juan Soto",
        "market": "hits+runs+rbi",
        "line": 1.5,
        "side": "HIGHER",
        "expected_participation": True,
        "role": "starting RF",
        "opportunity": "full game",
    }
    inputs.update(input_overrides)
    return PregameCandidate(
        prediction_id="prop-1",
        sport="MLB",
        game_id="evt-1",
        prediction_type="PLAYER_PROP",
        selection="Juan Soto HIGHER 1.5 H+R+RBI",
        market_key="player_hits_runs_rbi",
        independent_group_key="MLB:evt-1:PLAYER_PROP:Juan Soto",
        inputs=inputs,
        features={},
        provenance=(),
        context={"matchup": "vs RHP"},
    )


def test_complete_prop_passes_preyscan():
    state = PreyScan().evaluate(_prop())
    assert state.decision == "PASS"
    assert state.reasons == ()


@pytest.mark.parametrize("field", ["player", "market", "side"])
def test_missing_required_text_field_is_blocked(field):
    state = PreyScan().evaluate(_prop(**{field: ""}))
    assert state.decision == "BLOCKED"
    assert f"missing {field}" in state.reasons


def test_non_numeric_or_boolean_line_is_blocked():
    assert PreyScan().evaluate(_prop(line="1.5")).decision == "BLOCKED"
    assert PreyScan().evaluate(_prop(line=True)).decision == "BLOCKED"


@pytest.mark.parametrize("participation", [False, None])
def test_unconfirmed_participation_is_blocked(participation):
    state = PreyScan().evaluate(_prop(expected_participation=participation))
    assert state.decision == "BLOCKED"
    assert "expected participation not confirmed" in state.reasons


def test_missing_role_or_opportunity_passes_with_caution():
    role_state = PreyScan().evaluate(_prop(role=""))
    opportunity_state = PreyScan().evaluate(_prop(opportunity=""))
    assert role_state.decision == "PASS_WITH_CAUTION"
    assert "missing role evidence" in role_state.reasons
    assert opportunity_state.decision == "PASS_WITH_CAUTION"
    assert "missing opportunity evidence" in opportunity_state.reasons


def test_missing_matchup_context_passes_with_caution():
    candidate = _prop()
    candidate = PregameCandidate(
        prediction_id=candidate.prediction_id,
        sport=candidate.sport,
        game_id=candidate.game_id,
        prediction_type=candidate.prediction_type,
        selection=candidate.selection,
        market_key=candidate.market_key,
        independent_group_key=candidate.independent_group_key,
        inputs=candidate.inputs,
        features=candidate.features,
        provenance=candidate.provenance,
        context={},
    )
    state = PreyScan().evaluate(candidate)
    assert state.decision == "PASS_WITH_CAUTION"
    assert "missing matchup context" in state.reasons


def test_non_player_prop_is_not_given_prop_specific_failures():
    team = PregameCandidate(
        prediction_id="team-1",
        sport="MLB",
        game_id="evt-1",
        prediction_type="TEAM",
        selection="Cardinals",
        market_key="moneyline",
        independent_group_key="MLB:evt-1:TEAM",
        inputs={},
        features={},
        provenance=(),
        context={},
    )
    state = PreyScan().evaluate(team)
    assert state.decision == "PASS"
    assert state.reasons == ()
