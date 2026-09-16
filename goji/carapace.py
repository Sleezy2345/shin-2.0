from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import PregameCandidate, ValidationState


@dataclass(frozen=True)
class FreshnessPolicy:
    caution_after: timedelta = timedelta(minutes=30)
    block_after: timedelta = timedelta(minutes=90)
    future_tolerance: timedelta = timedelta(minutes=5)


class Carapace:
    def __init__(self, policy: FreshnessPolicy | None = None):
        self.policy = policy or FreshnessPolicy()

    def evaluate(self, candidate: PregameCandidate, *, now: datetime | None = None) -> ValidationState:
        now = now or datetime.now(timezone.utc)
        blocked: list[str] = []
        cautions: list[str] = []

        required_text = {
            "prediction_id": candidate.prediction_id,
            "sport": candidate.sport,
            "game_id": candidate.game_id,
            "prediction_type": candidate.prediction_type,
            "selection": candidate.selection,
            "market_key": candidate.market_key,
            "independent_group_key": candidate.independent_group_key,
        }
        for field, value in required_text.items():
            if not isinstance(value, str) or not value.strip():
                blocked.append(f"missing {field}")

        if not candidate.provenance:
            blocked.append("missing provenance")
        else:
            aware = [p for p in candidate.provenance if p.observed_at.tzinfo is not None]
            if len(aware) != len(candidate.provenance):
                blocked.append("provenance timestamp missing timezone")
            elif aware:
                freshest = max(p.observed_at for p in aware)
                age = now - freshest
                if age < -self.policy.future_tolerance:
                    blocked.append("provenance timestamp too far in future")
                elif age > self.policy.block_after:
                    blocked.append("evidence older than block threshold")
                elif age > self.policy.caution_after:
                    cautions.append("evidence older than caution threshold")

        conflict = str(candidate.context.get("conflict_level", "NONE")).strip().upper()
        if conflict == "CRITICAL":
            blocked.append("critical source conflict")
        elif conflict == "MEANINGFUL":
            cautions.append("meaningful source conflict")

        if blocked:
            return ValidationState("BLOCKED", tuple(blocked + cautions))
        if cautions:
            return ValidationState("PASS_WITH_CAUTION", tuple(cautions))
        return ValidationState("PASS")
