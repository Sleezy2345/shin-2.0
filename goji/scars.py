from typing import Any

from .models import ScarsDiagnosis


def build_observed_evidence(frozen: dict[str, Any], settlement_payload: dict[str, Any]) -> dict[str, Any]:
    context = frozen.get("context") or {}
    expectations = context.get("expectations") or {}
    actual_state = settlement_payload.get("actual_state") or {}
    grading_inputs = settlement_payload.get("grading_inputs") or {}

    comparisons: list[bool] = []
    observed: dict[str, Any] = {}

    if "winner" in expectations and "winner" in actual_state:
        expected_winner = expectations.get("winner")
        actual_winner = actual_state.get("winner")
        winner_match = expected_winner == actual_winner
        comparisons.append(winner_match)
        observed["winner"] = {
            "expected": expected_winner,
            "actual": actual_winner,
            "match": winner_match,
        }

    if "market_score" in expectations and "score" in grading_inputs:
        expected_score = expectations.get("market_score")
        actual_score = grading_inputs.get("score")
        score_match = expected_score == actual_score
        comparisons.append(score_match)
        observed["market_score"] = {
            "expected": expected_score,
            "actual": actual_score,
            "match": score_match,
        }

    data_issue = bool(actual_state.get("data_issue") or settlement_payload.get("data_issue"))
    unexpected_event = bool(actual_state.get("unexpected_event") or settlement_payload.get("unexpected_event"))

    observed["expectation_match"] = None if not comparisons else all(comparisons)
    observed["data_issue"] = data_issue
    observed["unexpected_event"] = unexpected_event
    return observed


class Scars:
    def diagnose(
        self,
        prediction_id: str,
        frozen: dict[str, Any],
        settlement: dict[str, Any],
        observed: dict[str, Any],
    ) -> ScarsDiagnosis:
        outcome = str(settlement.get("outcome") or "").upper()
        match = observed.get("expectation_match")
        data_issue = observed.get("data_issue") is True
        unexpected_event = observed.get("unexpected_event") is True

        if data_issue:
            expectation_quality = "UNKNOWN"
            reasoning_quality = "UNKNOWN"
            outcome_informativeness = "LOW"
            variance_class = "DATA_ISSUE"
            learning_value = 0.1
        elif unexpected_event:
            expectation_quality = "UNKNOWN" if match is None else ("GOOD" if match else "BAD")
            reasoning_quality = "UNKNOWN"
            outcome_informativeness = "LOW"
            variance_class = "UNEXPECTED_EVENT"
            learning_value = 0.2
        elif match is True:
            expectation_quality = "GOOD"
            reasoning_quality = "GOOD"
            outcome_informativeness = "HIGH"
            variance_class = "EXPECTED_VARIANCE" if outcome == "LOSS" else "UNKNOWN"
            learning_value = 0.8
        elif match is False:
            expectation_quality = "BAD"
            reasoning_quality = "BAD"
            outcome_informativeness = "HIGH"
            variance_class = "MODEL_MISS" if outcome == "LOSS" else "UNKNOWN"
            learning_value = 0.7 if outcome == "LOSS" else 0.4
        else:
            expectation_quality = "UNKNOWN"
            reasoning_quality = "UNKNOWN"
            outcome_informativeness = "LOW"
            variance_class = "UNKNOWN"
            learning_value = 0.2

        eligible = learning_value >= 0.4 and not data_issue and not unexpected_event
        expected_state = dict((frozen.get("context") or {}).get("expectations") or {})
        actual_state = dict(settlement.get("actual_state") or {})
        correction_hypothesis = dict((frozen.get("context") or {}).get("correction_hypothesis") or {})
        provenance = settlement.get("provenance") or []
        if not isinstance(provenance, list):
            provenance = [provenance]

        primary_failure = None
        if expectation_quality == "BAD":
            primary_failure = "EXPECTATION_MISS"
        elif data_issue:
            primary_failure = "DATA_ISSUE"
        elif unexpected_event:
            primary_failure = "UNEXPECTED_EVENT"

        payload = {
            "expected_state": expected_state,
            "actual_state": actual_state,
            "deltas": dict(observed),
            "primary_failure": primary_failure,
            "secondary_factors": [],
            "data_quality": {"data_issue": data_issue},
            "confidence_assessment": {},
            "calibration_assessment": {},
            "segment": {"segment_key": frozen.get("segment_key", "default")},
            "evidence": dict(observed),
            "provenance": provenance,
            "causal_confidence": None,
            "correction_hypothesis": correction_hypothesis,
            "evolve_action": {},
            "expectation_quality": expectation_quality,
            "reasoning_quality": reasoning_quality,
            "outcome_informativeness": outcome_informativeness,
            "variance_class": variance_class,
            "learning_value": learning_value,
            "eligible_for_pattern_learning": eligible,
            "learning_notes": {"outcome": outcome},
        }

        return ScarsDiagnosis(
            memory_id=f"scars:{prediction_id}",
            prediction_id=prediction_id,
            expectation_quality=expectation_quality,
            reasoning_quality=reasoning_quality,
            outcome_informativeness=outcome_informativeness,
            variance_class=variance_class,
            learning_value=learning_value,
            eligible_for_pattern_learning=eligible,
            payload=payload,
        )
