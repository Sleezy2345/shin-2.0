"""SHADOW tests use synthetic rows and cannot certify a real pregame slate."""
from datetime import datetime, timezone

from goji.models import MarketResult, Provenance, ResolvedOutcome
from goji.shadow import ShadowPostgame


START = datetime(2026, 9, 16, 18, tzinfo=timezone.utc)


def freeze(kind, ident):
    inputs = {"provider_event_id": "evt-1", "home_team": "Cardinals", "away_team": "Giants"}
    if kind == "PLAYER_PROP":
        inputs.update({"player": "Jane Doe", "market": "hits", "provider_odd_id": "odd-1", "line": 1.5, "side": "HIGHER"})
    return {
        "prediction_id": ident, "freeze_fingerprint": f"fingerprint-{ident}",
        "frozen_at": datetime(2026, 9, 16, 17, tzinfo=timezone.utc),
        "slate_id": "real-slate", "payload": {
            "record_kind": "PREDICTION", "slate_id": "real-slate", "sport": "MLB",
            "game_id": "game-1", "prediction_type": kind,
            "selection": "Cardinals" if kind == "TEAM" else "Jane Doe higher 1.5 hits",
            "inputs": inputs, "context": {"expectations": {}},
        },
    }


def event():
    return ResolvedOutcome(
        provider_event_id="evt-1", sport="MLB", finalized=True,
        home_team="Cardinals", away_team="Giants", home_score=5.0, away_score=3.0,
        market_results={"odd-1": MarketResult("odd-1", 2.0, True)}, players={},
        provenance=Provenance("SportsGameOdds", "evt-1", datetime(2026, 9, 16, 21, tzinfo=timezone.utc)),
        raw_reference={}, starts_at=START,
    )


class IsolatedGenome:
    def __init__(self, rows, *, replay=False):
        self.rows = rows
        self.saved = []
        self.replay = replay
        self.ready_calls = 0

    def ready(self):
        self.ready_calls += 1
        return {"schema": "SHADOW/0.3", "ready": True}

    def queue(self, slate_id=None):
        return self.rows

    def record(self, prediction_id, payload):
        self.saved.append((prediction_id, payload))
        return {"created": not self.replay, "observation_id": "obs-1", "revision_of": None,
                "learning_eligible": False}


class Results:
    def __init__(self, outcome=None):
        self.outcome = outcome or event()
        self.lookups = []

    def finalized_events(self, event_ids):
        self.lookups.append(event_ids)
        return [self.outcome]


def test_zero_queue_is_honest_zero_experience_and_fetches_no_events():
    genome = IsolatedGenome([])
    results = Results()
    report = ShadowPostgame(genome=genome, results_client=results).run("real-slate")
    assert report.mode == "SHADOW"
    assert report.items == ()
    assert genome.saved == []
    assert genome.ready_calls == 1
    assert results.lookups == []


def test_team_and_prop_share_evaluator_and_store_only_isolated_observations():
    genome = IsolatedGenome([freeze("TEAM", "team-1"), freeze("PLAYER_PROP", "prop-1")])
    results = Results()
    report = ShadowPostgame(genome=genome, results_client=results).run("real-slate")
    assert results.lookups == [["evt-1"]]
    assert len(genome.saved) == 2
    assert [entry[1]["grade"]["outcome"] for entry in genome.saved] == ["WIN", "WIN"]
    assert all(entry[1]["learning_eligible"] is False for entry in genome.saved)
    assert all(entry[1]["result"]["provider"] == "sportsgameodds" for entry in genome.saved)
    assert all(entry[1]["carapace"]["decision"] == "PASS" for entry in genome.saved)
    assert all(entry[1]["grade"]["status"] == "PROPOSED_SETTLEMENT" for entry in genome.saved)
    assert {item.status for item in report.items if item.phase == "SHADOW"} == {"OBSERVATION_RECORDED"}
    assert all(not hasattr(genome, name) for name in ("settle", "record_postmortem", "record_experience_evidence"))


def test_same_observation_is_reported_as_replay_not_new_experience():
    genome = IsolatedGenome([freeze("TEAM", "team-1")], replay=True)
    report = ShadowPostgame(genome=genome, results_client=Results()).run()
    assert len(genome.saved) == 1
    assert any(item.status == "REPLAY_IGNORED" for item in report.items)
    assert not any(item.status == "OBSERVATION_RECORDED" for item in report.items)


def test_postgame_freeze_is_blocked_before_persistence():
    row = freeze("TEAM", "team-1")
    row["frozen_at"] = datetime(2026, 9, 16, 19, tzinfo=timezone.utc)
    genome = IsolatedGenome([row])
    report = ShadowPostgame(genome=genome, results_client=Results()).run()
    assert genome.saved == []
    assert any(item.status == "UNRESOLVED" for item in report.items)


def test_missing_exact_prop_score_requires_review_and_never_writes():
    genome = IsolatedGenome([freeze("PLAYER_PROP", "prop-1")])
    absent = event().__class__(**{**event().__dict__, "market_results": {}})
    report = ShadowPostgame(genome=genome, results_client=Results(absent)).run()
    assert genome.saved == []
    assert any(item.status == "REVIEW_REQUIRED" for item in report.items)
