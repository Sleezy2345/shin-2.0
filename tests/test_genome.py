import pytest
import requests

from goji.config import GenomeConfig
from goji.genome import GenomeClient, GenomeError


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = "fake response"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.response


def _client(response):
    return GenomeClient(
        GenomeConfig(url="https://example.supabase.co", service_role_key="service-secret", timeout_seconds=4),
        session=FakeSession(response),
    )


def test_freeze_slate_calls_canonical_rpc():
    client = _client(FakeResponse({"status": "ok"}))
    result = client.freeze_slate("slate-1", [{"prediction_id": "pred-1"}], [])

    call = client.session.calls[0]
    assert call["url"].endswith("/rest/v1/rpc/genome_freeze_slate")
    assert call["json"] == {"p_slate_id": "slate-1", "p_predictions": [{"prediction_id": "pred-1"}], "p_blocked": []}
    assert result == {"status": "ok"}


def test_review_queue_calls_canonical_rpc():
    client = _client(FakeResponse([]))
    client.review_queue("slate-1")
    assert client.session.calls[0]["url"].endswith("/rest/v1/rpc/genome_review_queue")
    assert client.session.calls[0]["json"] == {"p_slate_id": "slate-1"}


def test_settle_payload_matches_canonical_signature():
    client = _client(FakeResponse({"status": "SETTLED"}))
    client.settle("settle-1", "pred-1", {"outcome": "WIN"}, "fp-1")
    call = client.session.calls[0]
    assert call["url"].endswith("/rest/v1/rpc/genome_settle")
    assert call["json"] == {
        "p_settlement_id": "settle-1",
        "p_prediction_id": "pred-1",
        "p_payload": {"outcome": "WIN"},
        "p_freeze_fingerprint": "fp-1",
    }


def test_mark_review_required_payload_matches_signature():
    client = _client(FakeResponse({"status": "REVIEW_REQUIRED"}))
    client.mark_review_required("pred-1", "slate-1", "ambiguous", {"kind": "prop"})
    call = client.session.calls[0]
    assert call["url"].endswith("/rest/v1/rpc/genome_mark_review_required")
    assert call["json"] == {
        "p_prediction_id": "pred-1",
        "p_slate_id": "slate-1",
        "p_reason": "ambiguous",
        "p_payload": {"kind": "prop"},
    }


def test_postmortem_and_molt_queues_use_canonical_rpcs():
    client = _client(FakeResponse([]))
    client.postmortem_queue("slate-1")
    assert client.session.calls[-1]["url"].endswith("/rest/v1/rpc/genome_postmortem_queue")
    assert client.session.calls[-1]["json"] == {"p_slate_id": "slate-1"}

    client.molt_queue("slate-1")
    assert client.session.calls[-1]["url"].endswith("/rest/v1/rpc/genome_molt_queue")
    assert client.session.calls[-1]["json"] == {"p_slate_id": "slate-1"}


def test_record_postmortem_and_hypothesis_use_canonical_rpcs():
    client = _client(FakeResponse({"status": "ok"}))
    client.record_postmortem("scars:pred-1", "pred-1", {"expectation_quality": "UNKNOWN"})
    assert client.session.calls[-1]["url"].endswith("/rest/v1/rpc/genome_record_postmortem")
    assert client.session.calls[-1]["json"] == {
        "p_memory_id": "scars:pred-1",
        "p_prediction_id": "pred-1",
        "p_payload": {"expectation_quality": "UNKNOWN"},
    }

    client.register_hypothesis({"hypothesis_id": "molt:1", "sport": "MLB"})
    assert client.session.calls[-1]["url"].endswith("/rest/v1/rpc/genome_register_experience_hypothesis")
    assert client.session.calls[-1]["json"] == {"p_payload": {"hypothesis_id": "molt:1", "sport": "MLB"}}


def test_record_experience_evidence_forwards_named_payload():
    client = _client(FakeResponse(1))
    payload = {
        "p_hypothesis_id": "molt:1",
        "p_prediction_id": "pred-1",
        "p_postmortem_memory_id": "scars:pred-1",
        "p_evidence_family": "bullpen",
        "p_evidence_direction": "SUPPORTS",
        "p_learning_value": 0.8,
        "p_independent_group_key": "game-1",
        "p_context": {},
        "p_notes": {},
    }
    client.record_experience_evidence(payload)
    assert client.session.calls[-1]["url"].endswith("/rest/v1/rpc/genome_record_experience_evidence")
    assert client.session.calls[-1]["json"] == payload


def test_rpc_failure_names_operation_without_leaking_secret():
    client = _client(FakeResponse({"message": "nope"}, status_code=500))
    with pytest.raises(GenomeError, match="genome_scoreboards") as exc:
        client.scoreboards("MLB")
    assert "service-secret" not in str(exc.value)


def test_scoreboards_payload_matches_canonical_signature():
    client = _client(FakeResponse([]))
    client.scoreboards("MLB")
    assert client.session.calls[0]["json"] == {"p_sport": "MLB"}


def test_wager_link_payload_matches_canonical_signature():
    client = _client(FakeResponse({"status": "ok"}))
    client.record_wager_link(
        wager_id="wager-1",
        prediction_id="pred-1",
        platform="Underdog",
        slip_id="slip-1",
        stake=5.0,
        metadata={"note": "test"},
    )
    assert client.session.calls[0]["url"].endswith("/rest/v1/rpc/genome_record_wager_link")
    assert client.session.calls[0]["json"] == {
        "p_wager_id": "wager-1",
        "p_prediction_id": "pred-1",
        "p_platform": "Underdog",
        "p_slip_id": "slip-1",
        "p_stake": 5.0,
        "p_metadata": {"note": "test"},
    }
