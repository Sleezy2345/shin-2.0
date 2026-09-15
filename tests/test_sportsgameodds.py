from datetime import timezone

import pytest
import requests

from goji.config import SportsGameOddsConfig
from goji.sportsgameodds import SportsGameOddsClient, SportsGameOddsError


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.last_request = None

    def get(self, url, *, headers, params, timeout):
        self.last_request = {"url": url, "headers": headers, "params": params, "timeout": timeout}
        if self.error:
            raise self.error
        return self.response


def test_events_authenticates_and_normalizes():
    session = FakeSession(FakeResponse({
        "data": [
            {
                "eventID": "evt-1",
                "leagueID": "MLB",
                "teams": {"home": {"name": "Cardinals"}, "away": {"name": "Giants"}},
                "startsAt": "2026-09-15T23:45:00Z",
            }
        ]
    }))
    client = SportsGameOddsClient(
        SportsGameOddsConfig(api_key="secret", base_url="https://example.test/v2", timeout_seconds=3),
        session=session,
    )

    events = client.events("MLB", odds_available=True, limit=5)

    assert events[0].event_id == "evt-1"
    assert events[0].home_team == "Cardinals"
    assert events[0].starts_at.tzinfo == timezone.utc
    assert session.last_request["headers"]["x-api-key"] == "secret"
    assert session.last_request["params"]["leagueID"] == "MLB"
    assert session.last_request["params"]["limit"] == 5


def test_timeout_is_wrapped_without_secret_leak():
    session = FakeSession(error=requests.Timeout("slow"))
    client = SportsGameOddsClient(SportsGameOddsConfig(api_key="do-not-leak"), session=session)

    with pytest.raises(SportsGameOddsError, match="events request failed") as exc:
        client.events("MLB")

    assert "do-not-leak" not in str(exc.value)
