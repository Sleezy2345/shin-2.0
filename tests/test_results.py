from datetime import datetime, timezone

from goji.models import MarketResult, Provenance, ResolvedOutcome
from goji.results import parse_sgo_result


def test_resolved_outcome_preserves_exact_market_score():
    result = ResolvedOutcome(
        provider_event_id="evt-1",
        sport="MLB",
        finalized=True,
        home_team="Cardinals",
        away_team="Giants",
        home_score=5.0,
        away_score=3.0,
        market_results={"prop-1": MarketResult("prop-1", 2.0, True)},
        players={"player-1": {"name": "John Doe"}},
        provenance=Provenance("SportsGameOdds", "evt-1", datetime(2026, 9, 16, tzinfo=timezone.utc)),
        raw_reference={"status": {"finalized": True}},
    )
    assert result.market_results["prop-1"].score == 2.0


def _event(starts_at):
    return {
        "eventID": "evt-1", "leagueID": "MLB",
        "teams": {"home": {"names": {"long": "Cardinals"}},
                  "away": {"names": {"long": "Giants"}}},
        "scores": {"home": 5, "away": 3},
        "status": {"finalized": True, "startsAt": starts_at},
    }


def test_result_preserves_provider_event_start_in_utc():
    result = parse_sgo_result(_event("2026-09-16T14:00:00-04:00"))
    assert result.starts_at == datetime(2026, 9, 16, 18, tzinfo=timezone.utc)


def test_missing_or_invalid_provider_start_is_unknown_not_invented():
    for value in (None, "bad timestamp", "2026-09-16T18:00:00"):
        assert parse_sgo_result(_event(value)).starts_at is None
