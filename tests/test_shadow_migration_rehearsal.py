"""Fail closed unless CI runs dependency-ordered SQL as a non-superuser migrator."""
from pathlib import Path


def test_rehearsal_runs_both_real_migrations_and_proves_login():
    script = Path('scripts/shadow_migration_rehearsal.sh').read_text()
    for required in ('--network none', 'trap cleanup EXIT',
                     'tests/sql/shadow_v03_fixture.sql',
                     '2026091601_postgame_intelligence.sql',
                     '2026091602_shadow_experience.sql',
                     'tests/sql/shadow_migration_checks.sql',
                     'PGPASSWORD=$shadow_password',
                     'goji_shadow_writer'):
        assert required in script
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in script


def test_rehearsal_is_in_public_runner_job_and_not_scheduled():
    workflow = Path('.github/workflows/goji-shadow-db-preflight.yml').read_text()
    assert 'bash scripts/shadow_migration_rehearsal.sh' in workflow
    assert 'schedule:' not in workflow
    assert 'runs-on: ubuntu-latest' in workflow
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in workflow


def test_rehearsal_checks_canonical_immutability_and_replay():
    fixture = Path('tests/sql/shadow_v03_fixture.sql').read_text()
    checks = Path('tests/sql/shadow_migration_checks.sql').read_text()
    assert 'NOSUPERUSER' in fixture
    for name in ('genome_shadow_record', 'genome_shadow_queue', 'genome_shadow_ready',
                 'genome_settle', 'genome_freeze_slate', 'session_user',
                 'revision_of', 'learning_eligible', 'shin2_settlements'):
        assert name in checks
