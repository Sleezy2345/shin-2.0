#!/usr/bin/env bash
# Disposable SQL integration rehearsal, not Supabase validation or production provisioning.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null
command -v openssl >/dev/null
container="goji-v03-migration-$$"
admin_password="$(openssl rand -hex 32)"
shadow_password="$(openssl rand -hex 32)"
cleanup() {
  docker rm --force "$container" >/dev/null 2>&1 || true
  unset admin_password shadow_password
}
trap cleanup EXIT
# No external network, no published ports, no production host or service credentials.
docker run --detach --rm --network none --name "$container" \
  --env "POSTGRES_PASSWORD=$admin_password" postgres:17-alpine >/dev/null
ready=0
for attempt in $(seq 1 45); do
  if docker exec -e "PGPASSWORD=$admin_password" "$container" \
      pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
[[ "$ready" == 1 ]] || { echo 'Disposable PostgreSQL did not start' >&2; exit 1; }
admin_psql() {
  docker exec -i -e "PGPASSWORD=$admin_password" "$container" \
    psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U postgres -d postgres "$@"
}
# Fixture tables belong to a disposable NO-SUPERUSER CREATEROLE role.
admin_psql < tests/sql/shadow_v03_fixture.sql
# Execute each real SQL file with current_user = non-superuser migrator, not postgres.
{ printf 'SET ROLE goji_migrator;\n'; cat supabase/migrations/2026091601_postgame_intelligence.sql; } | admin_psql
{ printf 'SET ROLE goji_migrator;\n'; cat supabase/migrations/2026091602_shadow_experience.sql; } | admin_psql
# Short-lived disposable credential, never in the migration or repository.
admin_psql -v "shadow_password=$shadow_password" <<'SQL'
ALTER ROLE goji_shadow_writer PASSWORD :'shadow_password';
SQL
# Authenticate over TCP as the LOGIN. Not SET ROLE or an admin impersonation.
docker exec -i -e "PGPASSWORD=$shadow_password" "$container" \
  psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U goji_shadow_writer -d postgres \
  < tests/sql/shadow_migration_checks.sql
# Canonical counts and append-only behavior enforced independently as database owner.
admin_psql <<'SQL'
DO $$ BEGIN
 IF (SELECT count(*) FROM public.shin2_verdicts)<>3 OR
    (SELECT count(*) FROM public.shin2_settlements)<>0 OR
    (SELECT count(*) FROM public.genome_experience_events)<>0 OR
    (SELECT count(*) FROM public.prediction_postmortems)<>0 OR
    (SELECT count(*) FROM public.genome_experience_hypotheses)<>0 OR
    (SELECT count(*) FROM public.genome_shadow_observations)<>2 OR
    (SELECT count(*) FROM public.genome_shadow_observations WHERE learning_eligible)<>0 OR
    (SELECT count(*) FROM public.genome_shadow_observations WHERE revision_of IS NOT NULL)<>1 THEN
   RAISE EXCEPTION 'canonical state or shadow revision counts changed unexpectedly';
 END IF;
 BEGIN
   UPDATE public.genome_shadow_observations SET lifecycle='OBSERVED';
   RAISE EXCEPTION 'observation UPDATE bypassed append-only trigger';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
   DELETE FROM public.genome_shadow_observations;
   RAISE EXCEPTION 'observation DELETE bypassed append-only trigger';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 IF EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
            WHERE r.rolname='goji_shadow_writer') THEN
   RAISE EXCEPTION 'SHADOW login inherited unexpected role';
 END IF;
END $$;
SQL
echo 'Disposable v0.3 prerequisite + SHADOW migration, restricted login and revision rehearsal passed (fixture only; no Supabase validation).'
