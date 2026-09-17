from typing import Any

from .models import ResolvedOutcome, ValidationState


class PostgameCarapace:
    def evaluate(self, result: ResolvedOutcome, frozen: dict[str, Any]) -> ValidationState:
        if not result.finalized:
            return ValidationState("BLOCKED", ("event is not finalized",))
        if not result.provenance.provider or not result.provenance.source_id:
            return ValidationState("BLOCKED", ("result provenance is missing",))

        inputs = frozen.get("inputs") or {}
        provider_event_id = inputs.get("provider_event_id")
        if not provider_event_id or str(provider_event_id) != result.provider_event_id:
            return ValidationState("REVIEW_REQUIRED", ("provider event identity mismatch",))
        if frozen.get("sport") != result.sport:
            return ValidationState("REVIEW_REQUIRED", ("sport identity mismatch",))

        if frozen.get("prediction_type") == "TEAM":
            if result.home_score is None or result.away_score is None:
                return ValidationState("REVIEW_REQUIRED", ("final team score is incomplete",))
            return ValidationState("PASS")

        if frozen.get("prediction_type") == "PLAYER_PROP":
            odd_id = inputs.get("provider_odd_id")
            market = result.market_results.get(str(odd_id)) if odd_id else None
            if market is None or not market.scoring_supported or market.score is None:
                return ValidationState("REVIEW_REQUIRED", ("exact supported market score is unavailable",))
            return ValidationState("PASS")

        return ValidationState("REVIEW_REQUIRED", ("unsupported prediction type",))
