from datetime import datetime, timezone
from pathlib import Path

from goji.models import Provenance, ResolvedOutcome
from goji.postgame import OperationalPostgame


class FakeGenome:
    def __init__(self, review):
        self.review = review
        self.writes = []

    def review_queue(self, slate_id=None):
        return list(self.review)

    def postmortem_queue(self, slate_id=None):
        return []

    def molt_queue(self, slate_id=None):
        return []


class FakeResults:
    def __init__(self):
        self.calls = []

    def finalized_events(self, event_ids):
        self.calls.append(list(event_ids))
        return [ResolvedOutcome(
            provider_event_id="evt-legacy",
            sport="MLB",
            finalized=True,
            home_team="Cardinals",
            away_team="Giants",
            home_score=5.0,
            away_score=3.0,
            market_results={},
            players={},
            provenance=Provenance("SportsGameOdds", "evt-legacy", datetime(2026, 9, 16, tzinfo=timezone.utc)),
            raw_reference={},
        )]


def test_audit_can_recover_provider_event_id_from_v02_sgo_provenance():
    frozen = {
        "sport": "MLB",
        "game_id": "internal-game",
        "prediction_type": "TEAM",
        "selection": "Cardinals",
        "market_key": "moneyline",
        "independent_group_key": "game-1",
        "inputs": {},
        "provenance": [{"provider": "SportsGameOdds", "source_id": "evt-legacy", "observed_at": "2026-09-16T00:00:00+00:00"}],
        "context": {},
        "capture_mode": "FULL_SLATE",
    }
    row = {
        "prediction_id": "legacy-pred",
        "slate_id": "legacy-slate",
        "freeze_fingerprint": "fp-legacy",
        "payload": frozen,
    }
    results = FakeResults()
    report = OperationalPostgame(genome=FakeGenome([row]), results_client=results).run("legacy-slate", mode="AUDIT")

    assert results.calls == [["evt-legacy"]]
    assert any(item.prediction_id == "legacy-pred" and item.status == "PROPOSED_SETTLEMENT" for item in report.items)


def test_migration_keeps_v02_full_slate_rows_visible_without_game_start_at():
    sql = Path("supabase/migrations/2026091601_postgame_intelligence.sql").read_text()
    assert "payload->>'capture_mode'='FULL_SLATE'" in sql
    assert "payload->>'game_start_at' is null" in sql
