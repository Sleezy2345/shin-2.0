"""Check that isolated PostgreSQL proof remains deliberately test-only."""
from pathlib import Path


def test_shadow_security_preflight_isolated_and_no_supabase_credentials():
    runner = Path('scripts/shadow_role_preflight.sh').read_text()
    assert '--network none' in runner
    assert 'postgres:17-alpine' in runner
    assert 'openssl rand -hex 32' in runner
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in runner
    assert 'SUPABASE_URL' not in runner
    assert 'trap cleanup EXIT' in runner
    assert 'tests/sql/shadow_role_setup.sql' in runner
    assert 'tests/sql/shadow_role_checks.sql' in runner


def test_shadow_permission_probe_uses_real_login_and_asserts_denials():
    setup = Path('tests/sql/shadow_role_setup.sql').read_text()
    checks = Path('tests/sql/shadow_role_checks.sql').read_text()
    assert 'CREATE ROLE goji_shadow_writer' in setup
    assert 'NOBYPASSRLS' in setup
    assert 'REVOKE ALL ON FUNCTION public.genome_settle' in setup
    assert 'REVOKE ALL ON FUNCTION public.genome_freeze_slate' in setup
    assert 'SECURITY DEFINER' in setup
    assert 'OWNER TO goji_shadow_gateway' in setup
    assert 'session_user' in checks
    assert 'SET ROLE postgres' in checks
    assert 'public.shin2_settlements' in checks
    assert 'public.shin2_verdicts' in checks
    assert 'public.genome_settle' in checks
    assert 'public.genome_freeze_slate' in checks
    assert 'public.genome_shadow_ready' in checks
    assert 'public.genome_shadow_record' in checks


def test_preflight_ci_is_separate_and_uses_only_public_free_runner():
    workflow = Path('.github/workflows/goji-shadow-db-preflight.yml').read_text()
    assert 'runs-on: ubuntu-latest' in workflow
    assert 'bash scripts/shadow_role_preflight.sh' in workflow
    assert 'permissions:' in workflow
    assert 'contents: read' in workflow
    assert 'schedule:' not in workflow
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in workflow
    assert 'GOJI_SHADOW_ENABLED' not in workflow
