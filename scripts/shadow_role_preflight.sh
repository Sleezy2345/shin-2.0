#!/usr/bin/env bash
# Disposable model check, NOT a production migration or a Supabase integration test.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null
command -v openssl >/dev/null
container="goji-shadow-preflight-$$"
admin_password="$(openssl rand -hex 32)"
shadow_password="$(openssl rand -hex 32)"
cleanup() {
  docker rm --force "$container" >/dev/null 2>&1 || true
  unset admin_password shadow_password
}
trap cleanup EXIT
# Deliberately no published port or outside network. Both passwords live only in this job.
docker run --detach --rm --network none --name "$container" \
  --env "POSTGRES_PASSWORD=$admin_password" postgres:17-alpine >/dev/null
ready=0
for attempt in $(seq 1 45); do
  if docker exec -e "PGPASSWORD=$admin_password" "$container" \
      pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo "Isolated PostgreSQL container did not become ready" >&2
  exit 1
fi
docker exec -i -e "PGPASSWORD=$admin_password" "$container" \
  psql -X -v ON_ERROR_STOP=1 -v "shadow_password=$shadow_password" \
  -h 127.0.0.1 -U postgres -d postgres < tests/sql/shadow_role_setup.sql
# Real login/authentication over TCP; never reuse administrator connection or SET ROLE.
docker exec -i -e "PGPASSWORD=$shadow_password" "$container" \
  psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U goji_shadow_writer -d postgres \
  < tests/sql/shadow_role_checks.sql
rows="$(docker exec -e "PGPASSWORD=$admin_password" "$container" \
  psql -X -qAt -h 127.0.0.1 -U postgres -d postgres \
  -c 'SELECT count(*) FROM public.genome_shadow_observations')"
[[ "$rows" == 1 ]] || { echo "Replay did not preserve one observation" >&2; exit 1; }
canonical="$(docker exec -e "PGPASSWORD=$admin_password" "$container" \
  psql -X -qAt -h 127.0.0.1 -U postgres -d postgres \
  -c 'SELECT (SELECT count(*) FROM public.shin2_verdicts)::text || '\''/'\'' || (SELECT count(*) FROM public.shin2_settlements)::text')"
[[ "$canonical" == '2/0' ]] || { echo "Canonical fixture data changed" >&2; exit 1; }
echo 'Disposable PostgreSQL role/ACL proof passed (synthetic schema only; no TLS or Supabase validation).'
