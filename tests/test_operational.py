from datetime import datetime, timedelta, timezone

from goji.models import PregameCandidate, Provenance
from goji.operational import OperationalPregame


NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


class FakeGenome:
    def __init__(self):
        self.calls = []

    def freeze_slate(self, slate_id, predictions, blocked):
        self.calls.append((slate_id, predictions, blocked))
        return {"status": "FROZEN", "slate_id": slate_id}


def _provenance(age_minutes=10):
    return (
        Provenance(
            provider="SportsGameOdds",
            source_id="evt-1",
            observed_at=NOW - timedelta(minutes=age_minutes),
        ),
    )


def _team(*, age_minutes=10, features=None):
    return PregameCandidate(
        prediction_id="team-1",
        sport="MLB",
        game_id="evt-1",
        prediction_type="TEAM",
        selection="Cardinals",
        market_key="moneyline",
        independent_group_key="MLB:evt-1:TEAM",
        inputs={"home_team": "Cardinals", "away_team": "Giants"},
        features=features or {},
        provenance=_provenance(age_minutes),
        context={"conflict_level": "NONE"},
    )


def _prop():
    return PregameCandidate(
        prediction_id="prop-1",
        sport="MLB",
        game_id="evt-1",
        prediction_type="PLAYER_PROP",
        selection="Juan Soto HIGHER 1.5 H+R+RBI",
        market_key="player_hits_runs_rbi",
        independent_group_key="MLB:evt-1:PLAYER_PROP:Juan Soto",
        inputs={
            "player": "Juan Soto",
            "market": "hits+runs+rbi",
            "line": 1.5,
            "side": "HIGHER",
            "expected_participation": True,
            "role": "starting RF",
            "opportunity": "full game",
        },
        features={"baseline_probability": 0.57, "market_implied_probability": 0.52},
        provenance=_provenance(),
        context={"conflict_level": "NONE", "matchup": "vs RHP"},
    )


def test_prepare_builds_canonical_prediction_and_does_not_write_genome():
    genome = FakeGenome()
    prepared = OperationalPregame(genome=genome).prepare(
        "2026-09-16-MLB",
        [_team(features={"baseline_probability": 0.58, "market_implied_probability": 0.55})],
        now=NOW,
    )

    assert genome.calls == []
    assert len(prepared.predictions) == 1
    assert prepared.blocked == ()
    item = prepared.predictions[0]
    assert item["prediction_id"] == "team-1"
    payload = item["payload"]
    assert payload["sport"] == "MLB"
    assert payload["game_id"] == "evt-1"
    assert payload["prediction_type"] == "TEAM"
    assert payload["independent_group_key"] == "MLB:evt-1:TEAM"
    assert payload["roar_action"] == "NO_ROAR"
    assert payload["model_status"] == "COLD_START"
    assert payload["model_probability"] == 0.58
    assert payload["market_implied_probability"] == 0.55
    assert payload["carapace_state"]["decision"] == "PASS"
    assert len(payload["provenance"]) == 1


def test_stale_candidate_is_blocked_and_never_becomes_prediction():
    prepared = OperationalPregame().prepare("2026-09-16-MLB", [_team(age_minutes=91)], now=NOW)

    assert prepared.predictions == ()
    assert len(prepared.blocked) == 1
    blocked = prepared.blocked[0]
    assert blocked["blocked_id"] == "2026-09-16-MLB:team-1:blocked"
    assert blocked["carapace_state"]["decision"] == "BLOCKED"
    assert blocked["prediction_type"] == "TEAM"


def test_player_prop_payload_satisfies_genome_prop_fields():
    prepared = OperationalPregame().prepare("2026-09-16-MLB", [_prop()], now=NOW)

    assert len(prepared.predictions) == 1
    payload = prepared.predictions[0]["payload"]
    assert payload["prediction_type"] == "PLAYER_PROP"
    assert payload["inputs"]["player"] == "Juan Soto"
    assert payload["inputs"]["market"] == "hits+runs+rbi"
    assert payload["inputs"]["line"] == 1.5
    assert payload["inputs"]["side"] == "HIGHER"
    assert payload["carapace_state"]["decision"] == "PASS"


def test_market_probability_never_becomes_model_probability():
    prepared = OperationalPregame().prepare(
        "2026-09-16-MLB",
        [_team(features={"market_implied_probability": 0.63})],
        now=NOW,
    )

    payload = prepared.predictions[0]["payload"]
    assert payload["market_implied_probability"] == 0.63
    assert payload["model_probability"] is None
    assert payload["model_status"] == "COLD_START"
    assert payload["roar_action"] == "NO_ROAR"


def test_freeze_is_one_explicit_genome_write_after_prepare():
    genome = FakeGenome()
    runner = OperationalPregame(genome=genome)
    prepared = runner.prepare("2026-09-16-MLB", [_team(), _prop()], now=NOW)

    result = runner.freeze(prepared)

    assert result == {"status": "FROZEN", "slate_id": "2026-09-16-MLB"}
    assert len(genome.calls) == 1
    slate_id, predictions, blocked = genome.calls[0]
    assert slate_id == "2026-09-16-MLB"
    assert predictions == list(prepared.predictions)
    assert blocked == list(prepared.blocked)
