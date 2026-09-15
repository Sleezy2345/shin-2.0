from datetime import datetime, timezone
from typing import Any

import requests

from .config import SportsGameOddsConfig
from .models import NormalizedEvent, Provenance


class SportsGameOddsError(RuntimeError):
    pass


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class SportsGameOddsClient:
    def __init__(self, config: SportsGameOddsConfig | None = None, *, session: requests.Session | Any | None = None):
        self.config = config or SportsGameOddsConfig.from_env()
        self.session = session or requests.Session()

    def events(self, league_id: str, odds_available: bool = True, limit: int = 5) -> list[NormalizedEvent]:
        try:
            response = self.session.get(
                f"{self.config.base_url.rstrip('/')}/events/",
                headers={"x-api-key": self.config.api_key},
                params={"leagueID": league_id, "oddsAvailable": str(odds_available).lower(), "limit": limit},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SportsGameOddsError(f"SportsGameOdds events request failed: {type(exc).__name__}") from exc

        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise SportsGameOddsError("SportsGameOdds events response missing data list")

        normalized: list[NormalizedEvent] = []
        observed_at = datetime.now(timezone.utc)
        for row in rows:
            try:
                event_id = str(row["eventID"])
                league = str(row.get("leagueID") or league_id)
                teams = row["teams"]
                home_team = str(teams["home"]["names"]["long"])
                away_team = str(teams["away"]["names"]["long"])
                starts_at = _parse_time(str(row["status"]["startsAt"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise SportsGameOddsError("Malformed SportsGameOdds event record") from exc

            normalized.append(
                NormalizedEvent(
                    event_id=event_id,
                    league=league,
                    home_team=home_team,
                    away_team=away_team,
                    starts_at=starts_at,
                    provenance=Provenance(
                        provider="SportsGameOdds",
                        source_id=event_id,
                        observed_at=observed_at,
                    ),
                )
            )
        return normalized
