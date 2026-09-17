#!/usr/bin/env bash
# Disposable role and TLS model check, NOT a production migration or Supabase integration test.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null
command -v openssl >/dev/null
container="goji-shadow-preflight-$$"
tls_dir="$(mktemp -d)"
admin_password="$(openssl rand -hex 32)"
shadow_password="$(openssl rand -hex 32)"
cleanup() {
  docker rm --force "$container" >/dev/null 2>&1 || true
  rm -rf -- "$tls_dir"
  unset admin_password shadow_password
}
trap cleanup EXIT
# Deliberately no published port or outside network; all credentials are test-only.
docker run --detach --rm --network none --name "$container" \
  --env "POSTGRES_PASSWORD=$admin_password" postgres:17-alpine >/dev/null
wait_for_database() {
  local ready=0
  for attempt in $(seq 1 45); do
    if docker exec -e "PGPASSWORD=$admin_password" "$container" \
        pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  [[ "$ready" == 1 ]] || { echo "Disposable PostgreSQL not ready" >&2; exit 1; }
}
wait_for_database
docker exec -i -e "PGPASSWORD=$admin_password" "$container" \
  psql -X -v ON_ERROR_STOP=1 -v "shadow_password=$shadow_password" \
  -h 127.0.0.1 -U postgres -d postgres < tests/sql/shadow_role_setup.sql

# Generate an ephemeral local CA and certificate with a single trusted hostname.
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -keyout "$tls_dir/ca.key" -out "$tls_dir/ca.crt" \
  -subj '/CN=Goji Disposable Test CA' >/dev/null 2>&1
openssl req -new -newkey rsa:2048 -nodes \
  -keyout "$tls_dir/server.key" -out "$tls_dir/server.csr" \
  -subj '/CN=localhost' >/dev/null 2>&1
printf 'subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n' > "$tls_dir/extensions.cnf"
openssl x509 -req -in "$tls_dir/server.csr" -CA "$tls_dir/ca.crt" \
  -CAkey "$tls_dir/ca.key" -CAcreateserial -out "$tls_dir/server.crt" \
  -days 1 -sha256 -extfile "$tls_dir/extensions.cnf" >/dev/null 2>&1
for filename in ca.crt server.crt server.key; do
  docker cp "$tls_dir/$filename" "$container:/tmp/goji-$filename"
done
# The PostgreSQL process needs an owner-only key; the host's ephemeral files remain private.
docker exec -u root "$container" sh -eu -c '
  cp /tmp/goji-server.key /var/lib/postgresql/data/server.key
  cp /tmp/goji-server.crt /var/lib/postgresql/data/server.crt
  chown postgres:postgres /var/lib/postgresql/data/server.key /var/lib/postgresql/data/server.crt
  chmod 0600 /var/lib/postgresql/data/server.key
  chmod 0644 /var/lib/postgresql/data/server.crt
  chmod 0644 /tmp/goji-ca.crt
'
for setting in "ssl = 'on'" \
               "ssl_cert_file = '/var/lib/postgresql/data/server.crt'" \
               "ssl_key_file = '/var/lib/postgresql/data/server.key'"; do
  docker exec -e "PGPASSWORD=$admin_password" "$container" \
    psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U postgres -d postgres \
    -c "ALTER SYSTEM SET $setting" >/dev/null
done
docker restart "$container" >/dev/null
wait_for_database
# hostaddr controls routing while host controls certificate hostname verification.
shadow_connection='host=localhost hostaddr=127.0.0.1 port=5432 dbname=postgres user=goji_shadow_writer sslmode=verify-full sslrootcert=/tmp/goji-ca.crt'
ssl_is_active="$(docker exec -e "PGPASSWORD=$shadow_password" "$container" \
  psql -X -qAt -v ON_ERROR_STOP=1 -d "$shadow_connection" \
  -c 'SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid = pg_backend_pid()')"
[[ "$ssl_is_active" == t ]] || { echo "SHADOW TLS was not negotiated" >&2; exit 1; }
if docker exec -e "PGPASSWORD=$shadow_password" "$container" \
   psql -X -qAt -v ON_ERROR_STOP=1 \
   -d 'host=wrong.example.invalid hostaddr=127.0.0.1 port=5432 dbname=postgres user=goji_shadow_writer sslmode=verify-full sslrootcert=/tmp/goji-ca.crt' \
   -c 'SELECT 1' >/dev/null 2>&1; then
  echo "Wrong TLS certificate hostname was accepted" >&2
  exit 1
fi
# Execute the privilege tests over an actually authenticated TLS connection.
docker exec -i -e "PGPASSWORD=$shadow_password" "$container" \
  psql -X -v ON_ERROR_STOP=1 -d "$shadow_connection" \
  < tests/sql/shadow_role_checks.sql
rows="$(docker exec -e "PGPASSWORD=$admin_password" "$container" \
  psql -X -qAt -h 127.0.0.1 -U postgres -d postgres \
  -c 'SELECT count(*) FROM public.genome_shadow_observations')"
[[ "$rows" == 1 ]] || { echo "Replay did not preserve one observation" >&2; exit 1; }
canonical="$(docker exec -e "PGPASSWORD=$admin_password" "$container" \
  psql -X -qAt -h 127.0.0.1 -U postgres -d postgres \
  -c 'SELECT (SELECT count(*) FROM public.shin2_verdicts)::text || '\''/'\'' || (SELECT count(*) FROM public.shin2_settlements)::text')"
[[ "$canonical" == '2/0' ]] || { echo "Canonical fixture data changed" >&2; exit 1; }
echo 'Disposable PostgreSQL login, permission, TLS and hostname proof passed (synthetic schema; no Supabase validation).'
