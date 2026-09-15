from goji.baseline import ColdStartBaseline
from goji.models import PredictionInput


def _input(features):
    return PredictionInput(
        prediction_id="pred-1",
        sport="MLB",
        prediction_type="TEAM",
        selection="Cardinals",
        features=features,
        provenance=(),
    )


def test_baseline_is_always_cold_start_and_no_roar():
    result = ColdStartBaseline().predict(_input({"baseline_probability": 0.63}))
    assert result.model_status == "COLD_START"
    assert result.roar_action == "NO_ROAR"
    assert result.model_probability == 0.63


def test_baseline_refuses_to_copy_market_probability_when_model_evidence_is_missing():
    result = ColdStartBaseline().predict(_input({"market_implied_probability": 0.71}))
    assert result.model_probability is None
    assert result.market_implied_probability == 0.71
    assert result.roar_action == "NO_ROAR"
    assert "insufficient" in result.reason.lower()
