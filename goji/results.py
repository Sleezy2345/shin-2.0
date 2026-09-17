from datetime import datetime, timezone
from typing import Any

from .models import MarketResult, Provenance, ResolvedOutcome


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _canonical_sport(value: Any) -> str:
    sport = str(value or "UNKNOWN").upper()
    if sport in {"NCAAF", "NCAA_FOOTBALL"}:
        return "CFB"
    return sport


def _provider_start(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def parse_sgo_result(row: dict[str, Any]) -> ResolvedOutcome:
    event_id = str(row["eventID"])
    teams = row["teams"]
    status = row.get("status") or {}
    scores = row.get("scores") or {}
    market_results: dict[str, MarketResult] = {}
    for key, value in (row.get("odds") or {}).items():
        if not isinstance(value, dict):
            continue
        odd_id = str(value.get("oddID") or key)
        market_results[odd_id] = MarketResult(
            odd_id=odd_id,
            score=_number(value.get("score")),
            scoring_supported=value.get("scoringSupported") is True,
        )

    return ResolvedOutcome(
        provider_event_id=event_id,
        sport=_canonical_sport(row.get("leagueID")),
        finalized=status.get("finalized") is True,
        home_team=str(teams["home"]["names"]["long"]),
        away_team=str(teams["away"]["names"]["long"]),
        home_score=_number(scores.get("home")),
        away_score=_number(scores.get("away")),
        market_results=market_results,
        players=dict(row.get("players") or {}),
        provenance=Provenance("SportsGameOdds", event_id, datetime.now(timezone.utc)),
        raw_reference={
            "status": dict(status),
            "scores": {"home": scores.get("home"), "away": scores.get("away")},
            "market_ids": sorted(market_results),
        },
        starts_at=_provider_start(status.get("startsAt")),
    )
