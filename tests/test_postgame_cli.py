import json
from pathlib import Path

import pytest

from goji.models import PostgameItem, PostgameRunReport


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, slate_id=None, *, mode="AUDIT"):
        self.calls.append({"slate_id": slate_id, "mode": mode})
        return PostgameRunReport(
            slate_id=slate_id, mode=mode,
            items=(PostgameItem("pred-1", "SETTLEMENT", "PROPOSED_SETTLEMENT", "ok", {"outcome": "WIN"}),),
        )


class FakeShadowRunner:
    def __init__(self):
        self.calls = []

    def run(self, slate_id=None):
        self.calls.append(slate_id)
        return PostgameRunReport(slate_id=slate_id, mode="SHADOW", items=())


SHADOW_ENV = {
    "GOJI_POSTGAME_MODE": "SHADOW", "GOJI_SHADOW_ENABLED": "true",
    "GOJI_SHADOW_DATABASE_URL": "postgresql://goji_shadow_writer:example-only@db.example.invalid:5432/postgres?sslmode=verify-full&sslrootcert=%2Ftmp%2Ftest-ca.crt",
    "GOJI_SLATE_ID": "slate-1",
}


def test_cli_defaults_to_audit_and_serializes_report():
    from scripts.goji_postgame import run_from_env
    runner = FakeRunner()
    output = run_from_env(runner=runner, environ={})
    assert runner.calls == [{"slate_id": None, "mode": "AUDIT"}]
    assert output["mode"] == "AUDIT"
    assert output["items"][0]["status"] == "PROPOSED_SETTLEMENT"
    json.dumps(output)


def test_cli_rejects_live_before_any_runner_is_called():
    from scripts.goji_postgame import run_from_env
    runner, shadow = FakeRunner(), FakeShadowRunner()
    with pytest.raises(SystemExit, match="AUDIT or SHADOW"):
        run_from_env(runner=runner, shadow_runner=shadow, environ={"GOJI_POSTGAME_MODE": "LIVE"})
    assert runner.calls == [] and shadow.calls == []


def test_shadow_requires_separate_enabled_login_even_with_service_key():
    from scripts.goji_postgame import run_from_env
    shadow = FakeShadowRunner()
    with pytest.raises(Exception, match="disabled"):
        run_from_env(shadow_runner=shadow, environ={"GOJI_POSTGAME_MODE": "SHADOW", "SUPABASE_SERVICE_ROLE_KEY": "unused-secret"})
    assert shadow.calls == []


def test_shadow_routes_only_to_injected_restricted_runner():
    from scripts.goji_postgame import run_from_env
    audit, shadow = FakeRunner(), FakeShadowRunner()
    output = run_from_env(runner=audit, shadow_runner=shadow, environ=SHADOW_ENV)
    assert audit.calls == []
    assert shadow.calls == ["slate-1"]
    assert output == {"slate_id": "slate-1", "mode": "SHADOW", "items": []}


def test_cli_rejects_unknown_mode_before_runner_call():
    from scripts.goji_postgame import run_from_env
    runner = FakeRunner()
    with pytest.raises(SystemExit, match="AUDIT or SHADOW"):
        run_from_env(runner=runner, environ={"GOJI_POSTGAME_MODE": "YOLO"})
    assert runner.calls == []


def test_initial_postgame_workflow_cannot_schedule_or_dispatch_live():
    workflow = Path(".github/workflows/goji-postgame.yml").read_text()
    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "          - LIVE" not in workflow
    assert "GOJI_POSTGAME_MODE: LIVE" not in workflow
    assert "          - SHADOW" in workflow
    assert "manual-shadow:" in workflow
    assert "GOJI_POSTGAME_MODE: AUDIT" in workflow
    assert "GOJI_POSTGAME_MODE: SHADOW" in workflow
    shadow_job = workflow.split("manual-shadow:", 1)[1]
    assert "SUPABASE_SERVICE_ROLE_KEY" not in shadow_job
    assert "GOJI_SHADOW_DATABASE_URL" in shadow_job
    assert "GOJI_SHADOW_ENABLED" in shadow_job
