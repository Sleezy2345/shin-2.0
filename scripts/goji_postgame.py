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


def run_from_env(*, runner: OperationalPostgame | Any | None = None, environ: Mapping[str, str] | None = None) -> dict:
    env = os.environ if environ is None else environ
    mode = str(env.get("GOJI_POSTGAME_MODE", "AUDIT")).upper()
    if mode not in {"AUDIT", "LIVE"}:
        raise SystemExit("GOJI_POSTGAME_MODE must be AUDIT or LIVE")
    slate_id = str(env.get("GOJI_SLATE_ID") or "").strip() or None
    active_runner = runner or OperationalPostgame()
    report = active_runner.run(slate_id, mode=mode)
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
