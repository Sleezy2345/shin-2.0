"""Static prerequisites: these do not replace executing the migration as the login."""
from pathlib import Path
import re

MIGRATION = Path('supabase/migrations/2026091602_shadow_experience.sql')


def test_shadow_migration_exists_after_postgame_dependency():
    assert Path('supabase/migrations/2026091601_postgame_intelligence.sql').exists()
    assert MIGRATION.exists(), 'real SHADOW migration must be authored before release'
    sql = MIGRATION.read_text().lower()
    assert 'genome_postgame_reviews' in sql
    assert 'genome_shadow_observations' in sql
    assert 'references public.shin2_verdicts' in sql


def test_shadow_migration_has_separate_low_privilege_roles_and_locked_rpcs():
    sql = MIGRATION.read_text().lower()
    for phrase in (
        'create role goji_shadow_writer', 'login noinherit nobypassrls',
        'create role goji_shadow_gateway', 'nologin noinherit nobypassrls',
        'enable row level security', 'create policy',
        'security definer', "set search_path = ''",
        'revoke all on function public.genome_shadow_ready()',
        'revoke all on function public.genome_shadow_queue(text)',
        'revoke all on function public.genome_shadow_record(text,jsonb)',
        'from public', 'to goji_shadow_writer',
    ):
        assert phrase in sql, phrase
    ddl = '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
    assert not re.search(r'\b(create|alter)\s+role\b[^;]*\bpassword\b', ddl), 'credentials must not appear in migration DDL'
    assert 'grant all on' not in ddl
    assert 'grant select on public.shin2_verdicts to goji_shadow_writer' not in ddl
    assert 'grant insert on public.shin2_settlements' not in ddl
    assert 'grant execute on function public.genome_settle' not in ddl
    assert 'grant execute on function public.genome_freeze_slate' not in ddl


def test_shadow_migration_never_mutates_canonical_outcomes():
    sql = MIGRATION.read_text().lower()
    for forbidden in (
        'insert into public.shin2_settlements',
        'update public.shin2_settlements',
        'insert into public.genome_experience_events',
        'insert into public.prediction_postmortems',
        'insert into public.genome_experience_hypotheses',
        'insert into public.genome_experience_evidence',
        'on public.shin2_settlements',
    ):
        assert forbidden not in sql, forbidden
    assert 'unique (prediction_id, freeze_fingerprint, evaluator_version, result_digest)' in sql
    assert 'genome_shadow_deny_mutation' in sql
