from datetime import datetime, timezone

from goji.models import MarketResult, Provenance, ResolvedOutcome
from goji.postgame import OperationalPostgame


class FakeGenome:
    def __init__(self, *, review=None, postmortems=None, molt=None):
        self.review = list(review or [])
        self.postmortems = list(postmortems or [])
        self.molt = list(molt or [])
        self.writes = []

    def review_queue(self, slate_id=None):
        return list(self.review)

    def postmortem_queue(self, slate_id=None):
        return list(self.postmortems)

    def molt_queue(self, slate_id=None):
        return list(self.molt)

    def settle(self, settlement_id, prediction_id, payload, freeze_fingerprint):
        self.writes.append(("settle", prediction_id, payload))
        return {"status": "SETTLED"}

    def mark_review_required(self, prediction_id, slate_id, reason, payload):
        self.writes.append(("review", prediction_id, reason))
        return {"status": "REVIEW_REQUIRED"}

    def record_postmortem(self, memory_id, prediction_id, payload):
        self.writes.append(("postmortem", prediction_id, payload))
        return {"status": "RECORDED"}

    def register_hypothesis(self, payload):
        self.writes.append(("hypothesis", payload["hypothesis_id"], payload))
        return payload

    def record_experience_evidence(self, payload):
        self.writes.append(("evidence", payload["p_prediction_id"], payload))
        return 1


class FakeResults:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def finalized_events(self, event_ids):
        self.calls.append(list(event_ids))
        return list(self.rows)


def _result(*, markets=None):
    return ResolvedOutcome(
        provider_event_id="evt-1",
        sport="MLB",
        finalized=True,
        home_team="Cardinals",
        away_team="Giants",
        home_score=5.0,
        away_score=3.0,
        market_results=markets or {},
        players={},
        provenance=Provenance("SportsGameOdds", "evt-1", datetime(2026, 9, 16, tzinfo=timezone.utc)),
        raw_reference={},
    )


def _team_row(prediction_id="pred-team"):
    payload = {
        "sport": "MLB",
        "game_id": "game-1",
        "prediction_type": "TEAM",
        "selection": "Cardinals",
        "market_key": "moneyline",
        "segment_key": "default",
        "independent_group_key": "game-1",
        "inputs": {"provider_event_id": "evt-1"},
        "context": {"expectations": {"winner": "Cardinals"}},
    }
    return {
        "prediction_id": prediction_id,
        "slate_id": "slate-1",
        "freeze_fingerprint": f"fp-{prediction_id}",
        "payload": payload,
    }


def _prop_row():
    payload = {
        "sport": "MLB",
        "game_id": "game-1",
        "prediction_type": "PLAYER_PROP",
        "selection": "John Doe over 1.5",
        "market_key": "hits",
        "segment_key": "default",
        "independent_group_key": "game-1",
        "inputs": {
            "provider_event_id": "evt-1",
            "provider_odd_id": "prop-1",
            "player": "John Doe",
            "market": "hits",
            "line": 1.5,
            "side": "OVER",
        },
        "context": {},
    }
    return {
        "prediction_id": "pred-prop",
        "slate_id": "slate-1",
        "freeze_fingerprint": "fp-prop",
        "payload": payload,
    }


def test_audit_runs_settlement_and_scars_in_memory_with_zero_writes():
    genome = FakeGenome(review=[_team_row()])
    runner = OperationalPostgame(genome=genome, results_client=FakeResults([_result()]))

    report = runner.run("slate-1", mode="AUDIT")

    assert genome.writes == []
    assert any(item.phase == "SETTLEMENT" and item.status == "PROPOSED_SETTLEMENT" for item in report.items)
    assert any(item.phase == "SCARS" and item.status == "PROPOSED_POSTMORTEM" for item in report.items)


def test_live_settles_only_passed_items_and_routes_ambiguous_prop_to_review():
    genome = FakeGenome(review=[_team_row(), _prop_row()])
    runner = OperationalPostgame(genome=genome, results_client=FakeResults([_result()]))

    report = runner.run("slate-1", mode="LIVE")

    settle_writes = [row for row in genome.writes if row[0] == "settle"]
    review_writes = [row for row in genome.writes if row[0] == "review"]
    assert [row[1] for row in settle_writes] == ["pred-team"]
    assert [row[1] for row in review_writes] == ["pred-prop"]
    assert any(item.prediction_id == "pred-prop" and item.status == "REVIEW_REQUIRED" for item in report.items)


def test_scars_retry_runs_when_settlement_queue_is_empty():
    frozen = _team_row()["payload"]
    settlement = {
        "outcome": "WIN",
        "actual_state": {"winner": "Cardinals", "home_score": 5.0, "away_score": 3.0},
        "grading_inputs": {},
        "provenance": [],
    }
    genome = FakeGenome(postmortems=[{
        "prediction_id": "pred-team",
        "slate_id": "slate-1",
        "verdict_payload": frozen,
        "settlement_payload": settlement,
        "freeze_fingerprint": "fp-team",
    }])
    runner = OperationalPostgame(genome=genome, results_client=FakeResults([]))

    runner.run("slate-1", mode="LIVE")

    assert any(row[0] == "postmortem" and row[1] == "pred-team" for row in genome.writes)


def test_molt_retry_runs_when_settlement_and_scars_queues_are_empty():
    frozen = _team_row()["payload"]
    postmortem = {
        "memory_id": "scars:pred-team",
        "prediction_id": "pred-team",
        "expectation_quality": "BAD",
        "reasoning_quality": "BAD",
        "outcome_informativeness": "HIGH",
        "variance_class": "MODEL_MISS",
        "learning_value": 0.8,
        "eligible_for_pattern_learning": True,
        "correction_hypothesis": {
            "family": "bullpen",
            "statement": "Bullpen freshness is overrated after repeated high-leverage usage.",
        },
    }
    genome = FakeGenome(molt=[{
        "memory_id": "scars:pred-team",
        "prediction_id": "pred-team",
        "slate_id": "slate-1",
        "verdict_payload": frozen,
        "postmortem": postmortem,
    }])
    runner = OperationalPostgame(genome=genome, results_client=FakeResults([]))

    runner.run("slate-1", mode="LIVE")

    assert any(row[0] == "hypothesis" for row in genome.writes)
    assert any(row[0] == "evidence" and row[1] == "pred-team" for row in genome.writes)


def test_invalid_mode_is_rejected_before_any_work():
    genome = FakeGenome(review=[_team_row()])
    runner = OperationalPostgame(genome=genome, results_client=FakeResults([_result()]))

    try:
        runner.run("slate-1", mode="YOLO")
    except ValueError as exc:
        assert "AUDIT or LIVE" in str(exc)
    else:
        raise AssertionError("invalid mode should fail")
    assert genome.writes == []
