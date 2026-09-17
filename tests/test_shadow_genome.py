"""Contract tests for the dedicated LOGIN client; never use production credentials."""
import json

import pytest

from goji.shadow_db_config import ShadowDatabaseConfig, ShadowDatabaseConfigError
from goji.shadow_genome import ShadowGenome, ShadowGenomeError


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.read_only = False
        self.cursor_object = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cursor_object


def test_disabled_config_never_opens_connection():
    called = []
    with pytest.raises(ShadowDatabaseConfigError, match="disabled"):
        ShadowGenome(environ={}, connector=lambda **kw: called.append(kw))
    assert called == []


def test_ready_and_queue_are_read_only_and_use_only_allowlisted_functions():
    sessions = []
    answers = [[{"status": {"schema": "SHADOW/0.3", "ready": True}}],
               [{"prediction_id": "pred-1", "freeze_fingerprint": "fp-1"}]]

    def connect(*args, **kwargs):
        assert args == ("postgresql://example-only",)
        assert kwargs["connect_timeout"] == 5
        session = FakeConnection(answers[len(sessions)])
        sessions.append(session)
        return session

    genome = ShadowGenome(config=ShadowDatabaseConfig("postgresql://example-only"), connector=connect)
    assert genome.ready()["ready"] is True
    assert genome.queue("slate-1")[0]["prediction_id"] == "pred-1"
    assert all(conn.read_only for conn in sessions)
    assert sessions[0].cursor_object.statements == [("SELECT public.genome_shadow_ready() AS status", None)]
    assert sessions[1].cursor_object.statements == [("SELECT * FROM public.genome_shadow_queue(%s)", ("slate-1",))]
    assert not hasattr(genome, "execute")


def test_record_is_one_parameterized_allowlisted_write_and_cannot_reveal_secret():
    conn = FakeConnection([{"result": {"created": True, "observation_id": "obs-1", "learning_eligible": False}}])
    genome = ShadowGenome(
        config=ShadowDatabaseConfig("postgresql://example-only"),
        connector=lambda *args, **kwargs: conn,
    )
    observation = {"freeze_fingerprint": "fp-1", "grade": {"outcome": "WIN"}}
    result = genome.record("pred-1", observation)
    assert result["created"] is True
    assert conn.read_only is False
    sql, params = conn.cursor_object.statements[0]
    assert sql == "SELECT public.genome_shadow_record(%s, %s::jsonb) AS result"
    assert params == ("pred-1", json.dumps(observation, sort_keys=True, allow_nan=False))
    assert len(conn.cursor_object.statements) == 1


def test_database_error_is_sanitized_and_does_not_fallback():
    def broken(*args, **kwargs):
        raise RuntimeError("password=top-secret DSN=postgresql://user:top-secret@host")

    genome = ShadowGenome(config=ShadowDatabaseConfig("postgresql://example-only"), connector=broken)
    with pytest.raises(ShadowGenomeError, match="SHADOW database operation failed") as exc:
        genome.queue()
    assert "top-secret" not in str(exc.value)
    assert "top-secret" not in repr(exc.value)
