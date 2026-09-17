from goji.models import ScarsDiagnosis
from goji.molt import Molt


def _diagnosis(*, learning_value=0.8, eligible=True, correction=None):
    correction = correction if correction is not None else {
        "family": "bullpen",
        "statement": "Bullpen freshness is overrated after repeated high-leverage usage.",
    }
    return ScarsDiagnosis(
        memory_id="scars:pred-1",
        prediction_id="pred-1",
        expectation_quality="BAD",
        reasoning_quality="BAD",
        outcome_informativeness="HIGH",
        variance_class="MODEL_MISS",
        learning_value=learning_value,
        eligible_for_pattern_learning=eligible,
        payload={"correction_hypothesis": correction},
    )


def _frozen():
    return {
        "sport": "MLB",
        "prediction_type": "TEAM",
        "market_key": "moneyline",
        "segment_key": "late-bullpen",
        "independent_group_key": "game-1",
        "context": {},
    }


def test_ineligible_diagnosis_does_not_create_hypothesis():
    assert Molt().propose(_diagnosis(eligible=False), _frozen()) is None


def test_low_learning_value_does_not_create_hypothesis():
    assert Molt().propose(_diagnosis(learning_value=0.3), _frozen()) is None


def test_missing_structured_correction_hypothesis_does_not_invent_one():
    assert Molt().propose(_diagnosis(correction={}), _frozen()) is None


def test_valid_correction_creates_shadow_observed_hypothesis_only():
    proposal = Molt().propose(_diagnosis(), _frozen())
    assert proposal is not None
    hypothesis = proposal.hypothesis_payload
    assert hypothesis["hypothesis_id"].startswith("molt:")
    assert hypothesis["sport"] == "MLB"
    assert hypothesis["prediction_type"] == "TEAM"
    assert hypothesis["segment_key"] == "late-bullpen"
    assert hypothesis["lifecycle_status"] == "OBSERVED"
    assert hypothesis["deployment_status"] == "SHADOW"
    assert hypothesis["human_approval_required"] is True
    assert hypothesis["graduation_recommendation"] == "NOT_READY"


def test_evidence_preserves_independence_learning_value_and_context():
    proposal = Molt().propose(_diagnosis(), _frozen())
    evidence = proposal.evidence_payload
    assert evidence["p_prediction_id"] == "pred-1"
    assert evidence["p_postmortem_memory_id"] == "scars:pred-1"
    assert evidence["p_evidence_family"] == "bullpen"
    assert evidence["p_evidence_direction"] == "SUPPORTS"
    assert evidence["p_learning_value"] == 0.8
    assert evidence["p_independent_group_key"] == "game-1"
    assert evidence["p_context"] == {
        "sport": "MLB",
        "prediction_type": "TEAM",
        "market_key": "moneyline",
        "segment_key": "late-bullpen",
    }


def test_same_pattern_produces_same_hypothesis_id():
    first = Molt().propose(_diagnosis(), _frozen())
    second = Molt().propose(_diagnosis(), _frozen())
    assert first.hypothesis_payload["hypothesis_id"] == second.hypothesis_payload["hypothesis_id"]
