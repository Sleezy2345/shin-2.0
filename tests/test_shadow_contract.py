from copy import deepcopy
from datetime import datetime, timezone

import pytest

from goji.models import MarketResult, Provenance, ResolvedOutcome
from goji.shadow_contract import eligible_shadow_freeze


START = datetime(2026, 9, 16, 18, tzinfo=timezone.utc)


def frozen_row(kind="TEAM"):
    inputs = {"provider_event_id": "evt-1"}
    if kind == "PLAYER_PROP":
        inputs.update({"provider_odd_id": "odd-1", "player": "Jane Doe", "market": "hits", "line": 1.5, "side": "HIGHER"})
    return {
        "prediction_id": "real-1", "freeze_fingerprint": "fp-1",
        "frozen_at": "2026-09-16T17:00:00+00:00", "slate_id": "slate-real",
        "payload": {
            "record_kind": "PREDICTION", "sport": "MLB", "prediction_type": kind,
            "selection": "Cardinals" if kind == "TEAM" else "Jane Doe higher than 1.5 hits",
            "inputs": inputs,
        },
    }


def result(**changes):
    values = dict(
        provider_event_id="evt-1", sport="MLB", finalized=True,
        home_team="Cardinals", away_team="Giants", home_score=5.0, away_score=3.0,
        market_results={"odd-1": MarketResult("odd-1", 2.0, True)}, players={},
        provenance=Provenance("SportsGameOdds", "evt-1", datetime(2026, 9, 16, 19, tzinfo=timezone.utc)),
        raw_reference={}, starts_at=START,
    )
    values.update(changes)
    return ResolvedOutcome(**values)


def test_real_team_freeze_passes_without_mutation():
    row = frozen_row()
    original = deepcopy(row)
    assert eligible_shadow_freeze(row, result()).decision == "PASS"
    assert row == original


@pytest.mark.parametrize("field,value", [
    ("frozen_at", "2026-09-16T19:00:00+00:00"),
    ("frozen_at", "not-a-date"),
    ("freeze_fingerprint", ""),
    ("slate_id", ""),
    ("prediction_id", ""),
])
def test_invalid_freeze_is_not_eligible(field, value):
    row = frozen_row()
    row[field] = value
    assert eligible_shadow_freeze(row, result()).decision != "PASS"


@pytest.mark.parametrize("key,value", [
    ("record_kind", "TEST"), ("record_kind", "SMOKE"),
    ("sport", "NFL"), ("selection", "Pirates"),
])
def test_invalid_frozen_payload_is_not_eligible(key, value):
    row = frozen_row()
    row["payload"][key] = value
    assert eligible_shadow_freeze(row, result()).decision != "PASS"


def test_missing_provider_event_id_is_not_eligible():
    row = frozen_row()
    del row["payload"]["inputs"]["provider_event_id"]
    assert eligible_shadow_freeze(row, result()).decision != "PASS"


@pytest.mark.parametrize("change", [
    {"starts_at": None}, {"finalized": False}, {"provider_event_id": "other"},
    {"sport": "NFL"}, {"home_team": "Pirates"},
    {"provenance": Provenance("", "evt-1", START)},
])
def test_unverifiable_result_is_not_eligible(change):
    assert eligible_shadow_freeze(frozen_row(), result(**change)).decision != "PASS"


def test_real_prop_requires_exact_supported_score():
    row = frozen_row("PLAYER_PROP")
    assert eligible_shadow_freeze(row, result()).decision == "PASS"
    for markets in ({}, {"odd-1": MarketResult("odd-1", None, True)},
                    {"odd-1": MarketResult("odd-1", 2, False)}):
        assert eligible_shadow_freeze(row, result(market_results=markets)).decision != "PASS"


@pytest.mark.parametrize("key,value", [
    ("provider_odd_id", None), ("player", ""), ("market", ""),
    ("line", True), ("line", "1.5"), ("side", "SIDEWAYS"),
])
def test_incomplete_prop_freeze_is_not_eligible(key, value):
    row = frozen_row("PLAYER_PROP")
    row["payload"]["inputs"][key] = value
    assert eligible_shadow_freeze(row, result()).decision != "PASS"
