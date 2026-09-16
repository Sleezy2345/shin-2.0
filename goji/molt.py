from hashlib import sha256
from typing import Any

from .models import MoltProposal, ScarsDiagnosis


class Molt:
    def propose(self, diagnosis: ScarsDiagnosis, frozen: dict[str, Any]) -> MoltProposal | None:
        if not diagnosis.eligible_for_pattern_learning or diagnosis.learning_value < 0.4:
            return None

        correction = diagnosis.payload.get("correction_hypothesis") or {}
        family = str(correction.get("family") or "").strip()
        statement = str(correction.get("statement") or "").strip()
        if not family or not statement:
            return None

        sport = str(frozen.get("sport") or "UNKNOWN")
        prediction_type = str(frozen.get("prediction_type") or "UNKNOWN")
        market_key = str(frozen.get("market_key") or "unknown")
        segment_key = str(frozen.get("segment_key") or "default")
        group_key = str(frozen.get("independent_group_key") or diagnosis.prediction_id)

        identity = "|".join((sport, prediction_type, market_key, family, statement))
        hypothesis_id = f"molt:{sha256(identity.encode('utf-8')).hexdigest()[:20]}"
        scope = {
            "sport": sport,
            "prediction_type": prediction_type,
            "market_key": market_key,
            "failure_family": family,
        }

        hypothesis_payload = {
            "hypothesis_id": hypothesis_id,
            "sport": sport,
            "prediction_type": prediction_type,
            "segment_key": segment_key,
            "hypothesis": statement,
            "scope": scope,
            "lifecycle_status": "OBSERVED",
            "deployment_status": "SHADOW",
            "predictive_evidence_status": "UNPROVEN",
            "causal_claim_status": "UNPROVEN",
            "graduation_recommendation": "NOT_READY",
            "human_approval_required": True,
        }
        evidence_payload = {
            "p_hypothesis_id": hypothesis_id,
            "p_prediction_id": diagnosis.prediction_id,
            "p_postmortem_memory_id": diagnosis.memory_id,
            "p_evidence_family": family,
            "p_evidence_direction": "SUPPORTS",
            "p_learning_value": diagnosis.learning_value,
            "p_independent_group_key": group_key,
            "p_context": {
                "sport": sport,
                "prediction_type": prediction_type,
                "market_key": market_key,
                "segment_key": segment_key,
            },
            "p_notes": {
                "expectation_quality": diagnosis.expectation_quality,
                "reasoning_quality": diagnosis.reasoning_quality,
                "variance_class": diagnosis.variance_class,
                "promotion_locked": True,
            },
        }
        return MoltProposal(hypothesis_payload=hypothesis_payload, evidence_payload=evidence_payload)
