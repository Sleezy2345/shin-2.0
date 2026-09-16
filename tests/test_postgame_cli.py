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
            slate_id=slate_id,
            mode=mode,
            items=(PostgameItem("pred-1", "SETTLEMENT", "PROPOSED_SETTLEMENT", "ok", {"outcome": "WIN"}),),
        )


def test_cli_defaults_to_audit_and_serializes_report():
    from scripts.goji_postgame import run_from_env

    runner = FakeRunner()
    output = run_from_env(runner=runner, environ={})

    assert runner.calls == [{"slate_id": None, "mode": "AUDIT"}]
    assert output["mode"] == "AUDIT"
    assert output["items"][0]["status"] == "PROPOSED_SETTLEMENT"
    json.dumps(output)


def test_cli_accepts_explicit_live_and_slate():
    from scripts.goji_postgame import run_from_env

    runner = FakeRunner()
    output = run_from_env(
        runner=runner,
        environ={"GOJI_POSTGAME_MODE": "LIVE", "GOJI_SLATE_ID": "slate-1"},
    )

    assert runner.calls == [{"slate_id": "slate-1", "mode": "LIVE"}]
    assert output["slate_id"] == "slate-1"


def test_cli_rejects_unknown_mode_before_runner_call():
    from scripts.goji_postgame import run_from_env

    runner = FakeRunner()
    with pytest.raises(SystemExit, match="AUDIT or LIVE"):
        run_from_env(runner=runner, environ={"GOJI_POSTGAME_MODE": "YOLO"})
    assert runner.calls == []


def test_initial_postgame_workflow_cannot_schedule_or_dispatch_live():
    workflow = Path(".github/workflows/goji-postgame.yml").read_text()
    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "          - LIVE" not in workflow
    assert "GOJI_POSTGAME_MODE: LIVE" not in workflow
    assert "GOJI_POSTGAME_MODE: AUDIT" in workflow
    assert "GOJI_SHADOW_MODE" not in workflow
    assert "manual-shadow:" not in workflow
    assert "SPORTSGAMEODDS_API_KEY" in workflow
    assert "SUPABASE_URL" in workflow
    assert "SUPABASE_SERVICE_ROLE_KEY" in workflow
