"""Pure, fail-closed eligibility checks for *proposed* SHADOW observations.

This module never updates a freeze or writes to GENOME. Database constraints and
restricted credentials must independently enforce these checks before deployment.
"""

from datetime import datetime, timezone
from math import isfinite
from typing import Any

from .models import ResolvedOutcome, ValidationState


def _parse_frozen_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return timestamp.astimezone(timezone.utc) if timestamp.tzinfo else None


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def eligible_shadow_freeze(row: dict[str, Any], result: ResolvedOutcome) -> ValidationState:
    """Validate immutable pregame identity before counting a shadow observation."""
    frozen = row.get("payload")
    if not isinstance(frozen, dict):
        return ValidationState("BLOCKED", ("canonical freeze payload is missing",))
    if not all(_nonempty(row.get(key)) for key in ("prediction_id", "freeze_fingerprint", "slate_id")):
        return ValidationState("BLOCKED", ("canonical freeze identity is incomplete",))
    record_kind = frozen.get("record_kind")
    if record_kind not in (None, "PREDICTION"):
        return ValidationState("BLOCKED", ("non-prediction record",))
    if record_kind != "PREDICTION" and frozen.get("capture_mode") != "FULL_SLATE":
        return ValidationState("BLOCKED", ("genuine full-slate freeze is required",))
    if frozen.get("prediction_type") not in {"TEAM", "PLAYER_PROP"}:
        return ValidationState("BLOCKED", ("unsupported prediction type",))
    if not _nonempty(frozen.get("selection")) or not _nonempty(frozen.get("sport")):
        return ValidationState("BLOCKED", ("frozen selection or sport is missing",))
    inputs = frozen.get("inputs")
    if not isinstance(inputs, dict) or not _nonempty(inputs.get("provider_event_id")):
        return ValidationState("BLOCKED", ("frozen provider event identity is missing",))
    frozen_at = _parse_frozen_time(row.get("frozen_at"))
    start_at = result.starts_at
    if frozen_at is None or start_at is None or start_at.tzinfo is None:
        return ValidationState("BLOCKED", ("verified pregame freeze and event start are required",))
    if frozen_at >= start_at.astimezone(timezone.utc):
        return ValidationState("BLOCKED", ("prediction was not frozen before event start",))
    if not result.finalized:
        return ValidationState("BLOCKED", ("event is not finalized",))
    provenance = result.provenance
    if (not _nonempty(provenance.provider) or not _nonempty(provenance.source_id)
            or provenance.provider.casefold() != "sportsgameodds"
            or provenance.source_id != result.provider_event_id
            or provenance.observed_at.tzinfo is None):
        return ValidationState("BLOCKED", ("verified result provenance is missing or inconsistent",))
    if inputs["provider_event_id"] != result.provider_event_id:
        return ValidationState("REVIEW_REQUIRED", ("provider event identity mismatch",))
    if frozen["sport"] != result.sport:
        return ValidationState("REVIEW_REQUIRED", ("sport identity mismatch",))
    if not _nonempty(result.home_team) or not _nonempty(result.away_team) or result.home_team == result.away_team:
        return ValidationState("REVIEW_REQUIRED", ("result team identities are incomplete",))
    for field, actual in (("home_team", result.home_team), ("away_team", result.away_team)):
        if field in inputs and inputs[field] != actual:
            return ValidationState("REVIEW_REQUIRED", ("frozen team identity mismatch",))

    if frozen["prediction_type"] == "TEAM":
        if frozen["selection"] not in {result.home_team, result.away_team}:
            return ValidationState("REVIEW_REQUIRED", ("team selection does not match result",))
        if result.home_score is None or result.away_score is None:
            return ValidationState("REVIEW_REQUIRED", ("final team score is unavailable",))
        return ValidationState("PASS")

    if any(not _nonempty(inputs.get(key)) for key in ("player", "market", "provider_odd_id")):
        return ValidationState("BLOCKED", ("exact frozen player and market identity is missing",))
    line = inputs.get("line")
    if isinstance(line, bool) or not isinstance(line, (int, float)) or not isfinite(line):
        return ValidationState("BLOCKED", ("exact frozen numeric prop line is missing",))
    if str(inputs.get("side") or "").upper() not in {"OVER", "UNDER", "HIGHER", "LOWER"}:
        return ValidationState("BLOCKED", ("unsupported frozen prop side",))
    market = result.market_results.get(inputs["provider_odd_id"])
    if (market is None or market.odd_id != inputs["provider_odd_id"]
            or market.scoring_supported is not True or market.score is None
            or not isinstance(market.score, (int, float)) or not isfinite(market.score)):
        return ValidationState("REVIEW_REQUIRED", ("exact supported final prop score is unavailable",))
    return ValidationState("PASS")
