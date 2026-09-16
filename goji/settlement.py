from typing import Any

from .models import ResolvedOutcome, SettlementDecision


class TeamSettlementEvaluator:
    version = "team-winner-v1"

    def evaluate(self, frozen: dict[str, Any], result: ResolvedOutcome) -> SettlementDecision:
        selection = str(frozen.get("selection") or "")
        if not selection or selection not in {result.home_team, result.away_team}:
            return SettlementDecision(
                "REVIEW_REQUIRED",
                "team selection does not match final result identity",
                {"selection": selection, "home_team": result.home_team, "away_team": result.away_team},
                self.version,
            )
        if result.home_score is None or result.away_score is None:
            return SettlementDecision(
                "REVIEW_REQUIRED",
                "final team score is incomplete",
                {"home_score": result.home_score, "away_score": result.away_score},
                self.version,
            )
        if result.home_score == result.away_score:
            return SettlementDecision(
                "REVIEW_REQUIRED",
                "tied final score has no v0.3 team-winner grading rule",
                {"home_score": result.home_score, "away_score": result.away_score},
                self.version,
            )

        winner = result.home_team if result.home_score > result.away_score else result.away_team
        outcome = "WIN" if selection == winner else "LOSS"
        return SettlementDecision(
            outcome,
            f"final winner is {winner}",
            {
                "selection": selection,
                "winner": winner,
                "home_team": result.home_team,
                "away_team": result.away_team,
                "home_score": result.home_score,
                "away_score": result.away_score,
            },
            self.version,
        )


class PlayerPropSettlementEvaluator:
    version = "player-prop-v1"

    def evaluate(self, frozen: dict[str, Any], result: ResolvedOutcome) -> SettlementDecision:
        inputs = frozen.get("inputs") or {}
        line = inputs.get("line")
        side = str(inputs.get("side") or "").upper()
        odd_id = inputs.get("provider_odd_id")

        if isinstance(line, bool) or not isinstance(line, (int, float)):
            return SettlementDecision("REVIEW_REQUIRED", "prop line is missing or invalid", {}, self.version)
        if side not in {"OVER", "UNDER"}:
            return SettlementDecision("REVIEW_REQUIRED", "prop side must be OVER or UNDER", {}, self.version)
        if not odd_id:
            return SettlementDecision("REVIEW_REQUIRED", "provider odd id is missing", {}, self.version)

        market = result.market_results.get(str(odd_id))
        if market is None or not market.scoring_supported or market.score is None:
            return SettlementDecision(
                "REVIEW_REQUIRED",
                "exact supported market score is unavailable",
                {"provider_odd_id": str(odd_id)},
                self.version,
            )

        score = market.score
        numeric_line = float(line)
        grading_inputs = {
            "provider_odd_id": str(odd_id),
            "side": side,
            "line": numeric_line,
            "score": score,
        }
        if score == numeric_line:
            return SettlementDecision("PUSH", "market score equals frozen line", grading_inputs, self.version)
        if side == "OVER":
            outcome = "WIN" if score > numeric_line else "LOSS"
        else:
            outcome = "WIN" if score < numeric_line else "LOSS"
        return SettlementDecision(outcome, "graded from exact provider market score", grading_inputs, self.version)
