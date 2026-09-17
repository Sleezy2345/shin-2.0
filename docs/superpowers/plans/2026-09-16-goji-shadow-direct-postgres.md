# Goji SHADOW Restricted Direct PostgreSQL Implementation Plan

> **Status update (2026-09-17):** Tasks 1–3 are implemented and pass exact-head CI plus disposable PostgreSQL migration/security rehearsal. Remaining gates are Supabase-hosted isolated validation and genuine completed TEAM + PLAYER_PROP slate verification. Production deployment, merge, recurring SHADOW, LIVE, and model promotion remain separately gated.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a truly least-privilege PostgreSQL login for append-only GENOME SHADOW observations without using the service role, changing production, or incurring costs before separate approvals.

**Architecture:** Keep canonical GENOME in one Supabase project, preserve the shared v0.3 pure evaluator and real freeze contract, but replace the unproven custom PostgREST/JWT writer with a direct TLS-verified PostgreSQL LOGIN. A narrow database gateway role owns carefully reviewed SHADOW functions, while the login has no direct table writes or canonical execution permissions. Initial work is a fail-closed config and offline tests only; permission proof and migrations are gated on an approved isolated database.

**Tech Stack:** Python 3.11, Python stdlib/pytest 8, PostgreSQL/Supabase, GitHub Actions. Add a pinned PostgreSQL driver only when building the isolated runtime and its exact version is verified.

**Spec:** `docs/superpowers/specs/2026-09-16-goji-shadow-direct-postgres-amendment.md`; all unchanged provisions of `docs/superpowers/specs/2026-09-16-goji-v0.3-shadow-experience-design.md` remain binding.

## Global Constraints

- Make changes only to PR #4 head `goji-v0.3-postgame-intelligence`; never change `main`.
- Do not modify any production data, roles, grants, tables, functions, tokens, connection settings or GitHub secrets, and do not create any paid branch or project without separate cost approval.
- Do not use `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_SHADOW_JWT`, `anon`, or `postgres` as the SHADOW runtime identity. Do not commit credentials or print complete DSNs.
- Preserve frozen verdicts, fingerprint, official settlements/triggers/experience/scoreboards, evidence eligibility, shared evaluator, idempotency, revisions and cold-start status.
- No LIVE/manual LIVE or schedule release; manual AUDIT remains zero-write and SHADOW defaults off. No real-slate readiness assertion without independently verified genuine TEAM and PLAYER_PROP freeze/result evidence.
- RED -> GREEN -> whole-suite CI at exact final head; distinguish offline contract checks from actual TLS, RLS or database permission tests. Stop instead of weakening access control when proof fails.

## Responsibility map

- `goji/shadow_db_config.py`: isolated fail-closed config parser, no DB connection or logging.
- `tests/test_shadow_db_config.py`: offline credential, username, SSL and non-disclosure regression tests.
- `supabase/migrations/2026091602_shadow_experience.sql`: **gated follow-up** dependency-ordered migration generated via installed CLI `supabase migration new` once isolated execution is approved. Must not be applied to production at this stage.
- `goji/shadow_genome.py`: **gated follow-up** strict three-operation psycopg client; no SQL or RPC escape hatch.
- `goji/shadow.py`: **gated follow-up** runner reusing `evaluate_candidate`, `eligible_shadow_freeze` and pure report logic.
- `.github/workflows/goji-postgame.yml`, `scripts/goji_postgame.py`, `README.md`: **gated follow-up** manual AUDIT/SHADOW only, no cron, no LIVE, no service role in SHADOW job.

---

### Task 1: Stage safe direct-connection configuration and test locally/CI (no database)

**Files:** Create `tests/test_shadow_db_config.py`; then create `goji/shadow_db_config.py`. Keep existing `goji/config.py` and its service-role production client unchanged to avoid regressions in AUDIT.

**Interface:** `ShadowDatabaseConfig.from_env(environ: Mapping[str,str] | None=None) -> ShadowDatabaseConfig`, with `dsn` field marked `repr=False`; no public methods that execute SQL. Read only `GOJI_SHADOW_ENABLED` and `GOJI_SHADOW_DATABASE_URL` from supplied mapping or `os.environ`.

- [ ] Write RED tests for disabled/unset flag, missing DSN despite existing service-role key, role other than `goji_shadow_writer`, malformed or missing password/host, `sslmode` other than `verify-full`, missing/nonabsolute `sslrootcert`, duplicate or unsupported query keys (especially `options`, `service`, `role`), fragment, and sanitized error/repr containing no credentials. Valid case uses a synthetic URL `postgresql://goji_shadow_writer:example-only@db.example.invalid:5432/postgres?sslmode=verify-full&sslrootcert=%2Ftmp%2Ftest-ca.crt` and test-only enable flag; no network call.
- [ ] Execute `python -m pytest tests/test_shadow_db_config.py -v`; expected RED due to missing module.
- [ ] Implement parser with stdlib `urllib.parse.urlsplit/parse_qsl/unquote`, require exact username and password, hostname, database path `/postgres`, port 5432 or 6543, allowed query keys exactly `sslmode` and `sslrootcert` (unique), `verify-full` and absolute CA path. Reject missing, malformed and disabled state using a fixed `ShadowDatabaseConfigError` message without including the URL. Use frozen dataclass, `dsn: str = field(repr=False)`. No `requests`, psycopg connection, secrets print or service-role fallback in this module.
- [ ] Execute targeted GREEN `python -m pytest tests/test_shadow_db_config.py -v`, then `python -m pytest -q && python scripts/goji_check.py` on the exact branch. Review diff for credential exposure. Commit on feature branch. If full branch checkout is unavailable, run isolated module tests locally **and** obtain GitHub Actions full-suite status at the exact commit; disclose that local full-suite verification could not run.

### Task 2: Stage SQL permission contract, then stop at isolated-environment gate

**Files after separate isolated-environment approval:** `supabase/migrations/2026091602_shadow_experience.sql`, `tests/test_shadow_migration.py`. Do not create or apply this migration as a speculative production-ready schema.

- [ ] Before writing SQL, use SELECT-only catalog queries to export exact freeze/settle signatures and definitions, table columns/constraints, RLS and policies, PUBLIC function grants, role memberships/SET ROLE ability, triggers and ownership. Explicitly verify there are no canonical RLS policies for shadow access and no baseline SHADOW objects.
- [ ] Obtain separate explicit approval for an isolated test environment, with cost and rollback details. If the Supabase CLI or PostgreSQL runtime is absent, do not claim a rehearsal.
- [ ] Write RED contract tests asserting explicit dependency on `2026091601_postgame_intelligence.sql`, `goji_shadow_writer LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`, password absent until approved provisioning, independent gateway `NOLOGIN NOBYPASSRLS`, no broad table grants, strict `REVOKE EXECUTE ... FROM PUBLIC`, explicit function allowlist and one replay unique key. Check no function writes to canonical settlements, training, hypotheses, scoreboards or postmortems.
- [ ] Create the migration using `supabase migration new shadow_experience` in an isolated checkout and set its ordering after `2026091601` (adjust resulting filename within the repo convention without conflicting with an existing migration). Create only one SHADOW observation table with FK to genuine canonical verdict, RLS, append-only trigger and verified narrow readiness/queue/record functions. A dedicated gateway role can SELECT canonical verdict rows only under a specific RLS policy; only gateway can INSERT isolated observations. Functions owned by gateway, search_path fixed and SQL inputs parameterized; login EXECUTE only on three functions. No plaintext password in migration. Harden database/schema TEMP/CREATE and PUBLIC grants. Do not alter default privileges across all canonical tables or functions without separate review.
- [ ] In isolated database, apply v0.3 dependency then exact SHADOW migration; provision a synthetic test password outside SQL artifact; connect through TLS `verify-full`; query `session_user/current_user`, role attributes, memberships, ACLs, policy behavior and forbidden operations as the **actual** login, not a superuser impersonation alone. Attempt forbidden direct SELECT/INSERT/UPDATE/DELETE, SET ROLE escalation, canonical `genome_settle` and `genome_freeze_slate`; assert permission denied. Test genuine test-only pregame freeze, exact provider identity, record, idempotent replay, conflicting payload and revision, missing evidence, immutable UPDATE/DELETE, no canonical row count/checksum change. Roll back or destroy the approved isolated test instance; check residue. Stop on any proof failure.

### Task 3: Gated runner, manual workflow and release checks

**Files after Task 2 actual proof:** `goji/shadow_genome.py`, `goji/shadow.py`, `tests/test_shadow_genome.py`, `tests/test_shadow.py`, `scripts/goji_postgame.py`, `tests/test_postgame_cli.py`, `.github/workflows/goji-postgame.yml`, README.

- [ ] Write RED client tests: absent driver/DSN/flag aborts before network, exact parameterized SQL for three functions only, query/readiness read-only transaction, record explicit write transaction, no generic SQL method, sanitized database exceptions, no service-key imports or fallbacks.
- [ ] Pin an available compatible psycopg 3 release and include it in the dependency strategy only after verification. Implement connection with the validated DSN, short timeouts and certificate validation at connection; never log DSN/password. Use bounded `SELECT public.genome_shadow_ready()`, `SELECT ... FROM public.genome_shadow_queue(%s)`, `SELECT public.genome_shadow_record(%s,...)` with bound parameters; no arbitrary query interface.
- [ ] Write RED runner tests for fail-closed disabled mode, real freeze validation, TEAM and PLAYER_PROP deterministic grades via shared pure evaluator, unsupported/missing evidence, idempotent replay and corrections, canonical writes never called, zero eligible means zero-experience honest report. Implement minimal SHADOW runner and run tests GREEN.
- [ ] Write RED CLI/workflow tests: remove LIVE in Python CLI, manual AUDIT/SHADOW only, feature flag defaults false, manual SHADOW receives only dedicated connection secret + CA and provider key, never service role; no cron. Implement, test and document without deploying or configuring secrets.
- [ ] Run full suite and GitHub CI on final head; review code, migrations, actual role proof and real-slate evidence. Separately request approvals for production backup/migration, secret provisioning, initial SHADOW writes, merge and later recurring schedule. Never conflate branch implementation with production readiness.

## Self-review / explicit unresolved checkpoints

Approved identity design can be staged without cost. No installed PostgreSQL server/CLI and no isolated Supabase branch were available at initial preflight; actual password login, SSL validation, RLS, RPC execution, migration rollback and genuine-slate tests **cannot** be claimed until Task 2 is separately authorized and executed. The original plan's Tasks 4-7 are superseded only where they require custom PostgREST JWT and HTTP shadow client. All remaining acceptance tests are additive and remain binding.
