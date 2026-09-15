from pathlib import Path
import subprocess
import sys


def test_smoke_script_runs_from_repo_root_without_installing_package():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/goji_check.py"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Goji import/configuration smoke check OK" in result.stdout
