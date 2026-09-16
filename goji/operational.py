from datetime import datetime
from typing import Any

from .baseline import ColdStartBaseline
from .carapace import Carapace
from .genome import GenomeClient
from .models import PredictionInput, PregameCandidate, PreparedSlate, ValidationState
from .preyscan import PreyScan


def _combine_states(*states: ValidationState) -> ValidationState:
    reasons: list[str] = []
    decision = "PASS"
    for state in states:
        reasons.extend(state.reasons)
        if state.decision == "BLOCKED":
            decision = "BLOCKED"
        elif state.decision == "PASS_WITH_CAUTION" and decision != "BLOCKED":
            decision = "PASS_WITH_CAUTION"
    return ValidationState(decision, tuple(reasons))


def _serialize_provenance(candidate: PregameCandidate) -> list[dict[str, str]]:
    return [
        {
            "provider": receipt.provider,
            "source_id": receipt.source_id,
            "observed_at": receipt.observed_at.isoformat(),
        }
        for receipt in candidate.provenance
    ]


class OperationalPregame:
    def __init__(
        self,
        *,
        carapace: Carapace | None = None,
        preyscan: PreyScan | None = None,
        predictor: ColdStartBaseline | None = None,
        genome: GenomeClient | Any | None = None,
    ):
        self.carapace = carapace or Carapace()
        self.preyscan = preyscan or PreyScan()
        self.predictor = predictor or ColdStartBaseline()
        self.genome = genome

    def prepare(
        self,
        slate_id: str,
        candidates: list[PregameCandidate] | tuple[PregameCandidate, ...],
        *,
        now: datetime | None = None,
    ) -> PreparedSlate:
        predictions: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []

        for candidate in candidates:
            carapace_state = self.carapace.evaluate(candidate, now=now)
            if candidate.prediction_type == "PLAYER_PROP":
                state = _combine_states(carapace_state, self.preyscan.evaluate(candidate))
            else:
                state = carapace_state

            provenance = _serialize_provenance(candidate)
            if state.decision == "BLOCKED":
                reason = "; ".join(state.reasons) or "blocked by validation"
                blocked.append(
                    {
                        "blocked_id": f"{slate_id}:{candidate.prediction_id}:blocked",
                        "sport": candidate.sport,
                        "game_id": candidate.game_id,
                        "prediction_type": candidate.prediction_type,
                        "market_key": candidate.market_key,
                        "reason": reason,
                        "carapace_state": state.as_dict(),
                        "provenance": provenance,
                        "context": dict(candidate.context),
                    }
                )
                continue

            decision = self.predictor.predict(
                PredictionInput(
                    prediction_id=candidate.prediction_id,
                    sport=candidate.sport,
                    prediction_type=candidate.prediction_type,
                    selection=candidate.selection,
                    features=dict(candidate.features),
                    provenance=candidate.provenance,
                )
            )
            predictions.append(
                {
                    "prediction_id": candidate.prediction_id,
                    "payload": {
                        "sport": candidate.sport,
                        "game_id": candidate.game_id,
                        "prediction_type": candidate.prediction_type,
                        "selection": candidate.selection,
                        "market_key": candidate.market_key,
                        "independent_group_key": candidate.independent_group_key,
                        "roar_action": decision.roar_action,
                        "model_status": decision.model_status,
                        "model_probability": decision.model_probability,
                        "market_implied_probability": decision.market_implied_probability,
                        "reason": decision.reason,
                        "inputs": dict(candidate.inputs),
                        "features": dict(candidate.features),
                        "provenance": provenance,
                        "carapace_state": state.as_dict(),
                        "context": dict(candidate.context),
                    },
                }
            )

        return PreparedSlate(slate_id=slate_id, predictions=tuple(predictions), blocked=tuple(blocked))

    def freeze(self, prepared: PreparedSlate) -> Any:
        client = self.genome or GenomeClient()
        return client.freeze_slate(
            prepared.slate_id,
            list(prepared.predictions),
            list(prepared.blocked),
        )
