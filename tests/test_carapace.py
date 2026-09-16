from datetime import datetime, timedelta, timezone

from goji.carapace import Carapace
from goji.models import PregameCandidate, Provenance


NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


def _candidate(*, age_minutes=10, conflict_level="NONE", provenance=True, independent_group_key="MLB:evt-1:TEAM"):
    receipts = ()
    if provenance:
        receipts = (
            Provenance(
                provider="SportsGameOdds",
                source_id="evt-1",
                observed_at=NOW - timedelta(minutes=age_minutes),
            ),
        )
    return PregameCandidate(
        prediction_id="pred-1",
        sport="MLB",
        game_id="evt-1",
        prediction_type="TEAM",
        selection="Cardinals",
        market_key="moneyline",
        independent_group_key=independent_group_key,
        inputs={"home_team": "Cardinals", "away_team": "Giants"},
        features={},
        provenance=receipts,
        context={"conflict_level": conflict_level},
    )


def test_clean_recent_evidence_passes():
    state = Carapace().evaluate(_candidate(), now=NOW)
    assert state.decision == "PASS"
    assert state.reasons == ()


def test_aging_evidence_passes_with_caution():
    state = Carapace().evaluate(_candidate(age_minutes=31), now=NOW)
    assert state.decision == "PASS_WITH_CAUTION"
    assert "evidence older than caution threshold" in state.reasons


def test_stale_evidence_is_blocked():
    state = Carapace().evaluate(_candidate(age_minutes=91), now=NOW)
    assert state.decision == "BLOCKED"
    assert "evidence older than block threshold" in state.reasons


def test_empty_provenance_is_blocked():
    state = Carapace().evaluate(_candidate(provenance=False), now=NOW)
    assert state.decision == "BLOCKED"
    assert "missing provenance" in state.reasons


def test_future_evidence_beyond_clock_tolerance_is_blocked():
    candidate = _candidate(age_minutes=-6)
    state = Carapace().evaluate(candidate, now=NOW)
    assert state.decision == "BLOCKED"
    assert "provenance timestamp too far in future" in state.reasons


def test_meaningful_source_conflict_requires_caution():
    state = Carapace().evaluate(_candidate(conflict_level="MEANINGFUL"), now=NOW)
    assert state.decision == "PASS_WITH_CAUTION"
    assert "meaningful source conflict" in state.reasons


def test_critical_source_conflict_is_blocked():
    state = Carapace().evaluate(_candidate(conflict_level="CRITICAL"), now=NOW)
    assert state.decision == "BLOCKED"
    assert "critical source conflict" in state.reasons


def test_missing_independent_group_is_blocked():
    state = Carapace().evaluate(_candidate(independent_group_key=""), now=NOW)
    assert state.decision == "BLOCKED"
    assert "missing independent_group_key" in state.reasons
