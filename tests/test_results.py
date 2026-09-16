from datetime import datetime, timezone

from goji.models import MarketResult, Provenance, ResolvedOutcome


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
