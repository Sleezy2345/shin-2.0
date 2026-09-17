import json
import os
from dataclasses import asdict
from pathlib import Path
import sys
from typing import Mapping, Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goji.postgame import OperationalPostgame
from goji.shadow import ShadowPostgame
from goji.shadow_db_config import ShadowDatabaseConfig
from goji.shadow_genome import ShadowGenome


def run_from_env(
    *,
    runner: OperationalPostgame | Any | None = None,
    shadow_runner: ShadowPostgame | Any | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict:
    env = os.environ if environ is None else environ
    mode = str(env.get("GOJI_POSTGAME_MODE", "AUDIT")).upper()
    if mode not in {"AUDIT", "SHADOW"}:
        raise SystemExit("GOJI_POSTGAME_MODE must be AUDIT or SHADOW")
    slate_id = str(env.get("GOJI_SLATE_ID") or "").strip() or None

    if mode == "SHADOW":
        # Validate the independent restricted login even when a runner is injected.
        # This prevents tests/callers from accidentally treating service-role config
        # as authorization for SHADOW.
        config = ShadowDatabaseConfig.from_env(env)
        active_runner = shadow_runner or ShadowPostgame(genome=ShadowGenome(config=config))
        report = active_runner.run(slate_id)
    else:
        active_runner = runner or OperationalPostgame()
        report = active_runner.run(slate_id, mode="AUDIT")

    return {
        "slate_id": report.slate_id,
        "mode": report.mode,
        "items": [asdict(item) for item in report.items],
    }


def main() -> int:
    output = run_from_env()
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
