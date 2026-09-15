from .models import PredictionDecision, PredictionInput


class ColdStartBaseline:
    def predict(self, data: PredictionInput) -> PredictionDecision:
        raw_probability = data.features.get("baseline_probability")
        market_probability = data.features.get("market_implied_probability")

        model_probability: float | None = None
        reason = "Insufficient independent pregame evidence for a model probability."
        if isinstance(raw_probability, (int, float)) and 0 <= float(raw_probability) <= 1:
            model_probability = float(raw_probability)
            reason = "Illustrative cold-start baseline from supplied pregame features."

        return PredictionDecision(
            prediction_id=data.prediction_id,
            selection=data.selection,
            model_probability=model_probability,
            market_implied_probability=float(market_probability) if isinstance(market_probability, (int, float)) else None,
            model_status="COLD_START",
            roar_action="NO_ROAR",
            reason=reason,
        )
