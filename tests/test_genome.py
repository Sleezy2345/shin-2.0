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
