from goji.scars import Scars, build_observed_evidence


def _settlement(outcome="WIN", winner="Cardinals", score=None, **actual_overrides):
    actual_state = {"winner": winner}
    actual_state.update(actual_overrides)
    grading_inputs = {}
    if score is not None:
        grading_inputs["score"] = score
    return {"outcome": outcome, "actual_state": actual_state, "grading_inputs": grading_inputs}


def test_explicit_expected_winner_matches_actual_winner():
    frozen = {"context": {"expectations": {"winner": "Cardinals"}}}
    settlement = _settlement(outcome="WIN", winner="Cardinals")
    observed = build_observed_evidence(frozen, settlement)
    diagnosis = Scars().diagnose("pred-1", frozen, settlement, observed)
    assert observed["expectation_match"] is True
    assert diagnosis.expectation_quality == "GOOD"
    assert diagnosis.reasoning_quality == "GOOD"
    assert diagnosis.learning_value == 0.8


def test_explicit_expected_winner_miss_is_bad_expectation():
    frozen = {"context": {"expectations": {"winner": "Cardinals"}}}
    settlement = _settlement(outcome="LOSS", winner="Giants")
    diagnosis = Scars().diagnose("pred-1", frozen, settlement, build_observed_evidence(frozen, settlement))
    assert diagnosis.expectation_quality == "BAD"
    assert diagnosis.reasoning_quality == "BAD"
    assert diagnosis.learning_value == 0.7


def test_no_comparable_expectation_is_unknown_low_learning_value():
    frozen = {"context": {}}
    settlement = _settlement(outcome="WIN", winner="Cardinals")
    observed = build_observed_evidence(frozen, settlement)
    diagnosis = Scars().diagnose("pred-1", frozen, settlement, observed)
    assert observed["expectation_match"] is None
    assert diagnosis.expectation_quality == "UNKNOWN"
    assert diagnosis.learning_value == 0.2
    assert diagnosis.eligible_for_pattern_learning is False


def test_market_score_expectation_compares_only_observable_score():
    frozen = {"context": {"expectations": {"market_score": 2.0}}}
    settlement = _settlement(outcome="WIN", score=2.0)
    observed = build_observed_evidence(frozen, settlement)
    assert observed["expectation_match"] is True


def test_data_issue_is_low_value_and_not_pattern_eligible():
    frozen = {"context": {"expectations": {"winner": "Cardinals"}}}
    settlement = _settlement(outcome="LOSS", winner="Giants", data_issue=True)
    diagnosis = Scars().diagnose("pred-1", frozen, settlement, build_observed_evidence(frozen, settlement))
    assert diagnosis.variance_class == "DATA_ISSUE"
    assert diagnosis.reasoning_quality == "UNKNOWN"
    assert diagnosis.learning_value == 0.1
    assert diagnosis.eligible_for_pattern_learning is False


def test_unexpected_event_is_low_value_and_not_pattern_eligible():
    frozen = {"context": {"expectations": {"winner": "Cardinals"}}}
    settlement = _settlement(outcome="LOSS", winner="Giants", unexpected_event=True)
    diagnosis = Scars().diagnose("pred-1", frozen, settlement, build_observed_evidence(frozen, settlement))
    assert diagnosis.variance_class == "UNEXPECTED_EVENT"
    assert diagnosis.reasoning_quality == "UNKNOWN"
    assert diagnosis.learning_value == 0.2
    assert diagnosis.eligible_for_pattern_learning is False


def test_win_with_bad_expectation_is_not_good_reasoning():
    frozen = {"context": {"expectations": {"winner": "Cardinals"}}}
    settlement = _settlement(outcome="WIN", winner="Giants")
    diagnosis = Scars().diagnose("pred-1", frozen, settlement, build_observed_evidence(frozen, settlement))
    assert diagnosis.expectation_quality == "BAD"
    assert diagnosis.reasoning_quality == "BAD"
    assert diagnosis.learning_value == 0.4


def test_loss_with_good_expectation_is_not_automatically_model_miss():
    frozen = {"context": {"expectations": {"winner": "Cardinals"}}}
    settlement = _settlement(outcome="LOSS", winner="Cardinals")
    diagnosis = Scars().diagnose("pred-1", frozen, settlement, build_observed_evidence(frozen, settlement))
    assert diagnosis.expectation_quality == "GOOD"
    assert diagnosis.reasoning_quality == "GOOD"
    assert diagnosis.variance_class != "MODEL_MISS"
