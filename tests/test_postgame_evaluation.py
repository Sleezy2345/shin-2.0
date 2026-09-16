from pathlib import Path
from datetime import datetime, timezone

from goji.models import MarketResult, Provenance, ResolvedOutcome
from goji.molt import Molt
from goji.postgame_carapace import PostgameCarapace
from goji.scars import Scars
from goji.settlement import TeamSettlementEvaluator, PlayerPropSettlementEvaluator
from goji.postgame_evaluation import evaluate_candidate
from goji.postgame import OperationalPostgame


def _row(kind="TEAM"):
    inputs = {"provider_event_id": "evt-1"}
    if kind == "PLAYER_PROP":
        inputs.update({"provider_odd_id": "odd-1", "player": "Jane Doe", "market": "hits", "line": 1.5, "side": "OVER"})
    return {"prediction_id": "pred-1", "freeze_fingerprint": "fp-1", "slate_id": "slate-1", "payload": {
        "sport": "MLB", "prediction_type": kind, "selection": "Cardinals" if kind == "TEAM" else "Jane Doe over hits",
        "market_key": "hits" if kind == "PLAYER_PROP" else "moneyline",
        "inputs": inputs, "context": {"expectations": {"winner": "Cardinals"}} if kind == "TEAM" else {},
    }}


def _result(**updates):
    fields = dict(provider_event_id="evt-1", sport="MLB", finalized=True,
                  home_team="Cardinals", away_team="Giants", home_score=5.0, away_score=3.0,
                  market_results={"odd-1": MarketResult("odd-1", 2.0, True)}, players={},
                  provenance=Provenance("SportsGameOdds", "evt-1", datetime(2026, 9, 16, tzinfo=timezone.utc)), raw_reference={})
    fields.update(updates)
    return ResolvedOutcome(**fields)


def _evaluate(row, result):
    return evaluate_candidate(row, result, carapace=PostgameCarapace(),
        team_evaluator=TeamSettlementEvaluator(), prop_evaluator=PlayerPropSettlementEvaluator(),
        scars=Scars(), molt=Molt())


def test_team_and_prop_share_one_pure_proposed_grade():
    team, diagnosis, _ = _evaluate(_row(), _result())
    assert team.status == "PROPOSED_SETTLEMENT"
    assert team.payload["outcome"] == "WIN"
    assert diagnosis is not None and diagnosis.prediction_id == "pred-1"
    prop, prop_diagnosis, _ = _evaluate(_row("PLAYER_PROP"), _result())
    assert prop.status == "PROPOSED_SETTLEMENT"
    assert prop.payload["outcome"] == "WIN"
    assert prop_diagnosis is not None


def test_missing_exact_prop_market_and_nonfinal_cannot_be_diagnosed():
    for row, result, state in [
        (_row("PLAYER_PROP"), _result(market_results={}), "REVIEW_REQUIRED"),
        (_row(), _result(finalized=False), "UNRESOLVED"),
        (_row("OTHER"), _result(), "REVIEW_REQUIRED"),
    ]:
        item, diagnosis, proposal = _evaluate(row, result)
        assert item.status == state
        assert diagnosis is None
        assert proposal is None


def test_shared_evaluator_does_not_import_or_write_genome():
    source = Path("goji/postgame_evaluation.py").read_text()
    assert "from .genome" not in source
    assert "GenomeClient" not in source
    assert "genome.settle(" not in source


def test_proposed_settlement_and_scars_equal_audit_output():
    row = _row()
    expected, diagnosis, _ = _evaluate(row, _result())

    class Genome:
        def review_queue(self, slate_id=None):
            return [row]
        def postmortem_queue(self, slate_id=None):
            return []
        def molt_queue(self, slate_id=None):
            return []
        def __getattr__(self, name):
            raise AssertionError("AUDIT cannot write to GENOME: " + name)

    class Results:
        def finalized_events(self, ids):
            assert ids == ["evt-1"]
            return [_result()]

    audit = OperationalPostgame(genome=Genome(), results_client=Results()).run("slate-1", mode="AUDIT")
    settled = next(item for item in audit.items if item.phase == "SETTLEMENT")
    scars = next(item for item in audit.items if item.phase == "SCARS")
    assert settled.payload == expected.payload
    assert scars.payload == diagnosis.payload
