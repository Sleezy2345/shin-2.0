from .models import PregameCandidate, ValidationState


class PreyScan:
    def evaluate(self, candidate: PregameCandidate) -> ValidationState:
        if candidate.prediction_type != "PLAYER_PROP":
            return ValidationState("PASS")

        blocked: list[str] = []
        cautions: list[str] = []
        inputs = candidate.inputs

        for field in ("player", "market", "side"):
            value = inputs.get(field)
            if not isinstance(value, str) or not value.strip():
                blocked.append(f"missing {field}")

        line = inputs.get("line")
        if isinstance(line, bool) or not isinstance(line, (int, float)):
            blocked.append("invalid line")

        if inputs.get("expected_participation") is not True:
            blocked.append("expected participation not confirmed")

        role = inputs.get("role")
        if not isinstance(role, str) or not role.strip():
            cautions.append("missing role evidence")

        opportunity = inputs.get("opportunity")
        if not isinstance(opportunity, str) or not opportunity.strip():
            cautions.append("missing opportunity evidence")

        matchup = candidate.context.get("matchup")
        if not isinstance(matchup, str) or not matchup.strip():
            cautions.append("missing matchup context")

        if blocked:
            return ValidationState("BLOCKED", tuple(blocked + cautions))
        if cautions:
            return ValidationState("PASS_WITH_CAUTION", tuple(cautions))
        return ValidationState("PASS")
