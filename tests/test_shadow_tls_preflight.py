"""Regression contract: the disposable role probe must exercise real TLS.

Only checks the test harness; a real Supabase TLS connection is a distinct release gate.
"""
from pathlib import Path


def test_preflight_requires_verified_hostname_and_inspects_actual_connection():
    script = Path("scripts/shadow_role_preflight.sh").read_text()
    assert "sslmode=verify-full" in script
    assert "sslrootcert=" in script
    assert "pg_catalog.pg_stat_ssl" in script
    assert "ssl_is_active" in script
    assert "server.crt" in script
    assert "server.key" in script


def test_preflight_rejects_wrong_hostname_and_destroys_test_certificates():
    script = Path("scripts/shadow_role_preflight.sh").read_text()
    assert "wrong.example.invalid" in script
    assert "hostaddr=127.0.0.1" in script
    assert "mktemp -d" in script
    assert "rm -rf" in script
    assert "--network none" in script
    assert "SUPABASE_SERVICE_ROLE_KEY" not in script
