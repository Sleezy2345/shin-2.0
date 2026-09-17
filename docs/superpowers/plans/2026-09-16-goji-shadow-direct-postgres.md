# Goji SHADOW Restricted Direct PostgreSQL Implementation Plan

> **Status update (2026-09-17):** Tasks 1–3 are implemented on `goji-v0.3-postgame-intelligence` and verified on disposable PostgreSQL. The remaining blockers are Supabase-hosted isolated-environment proof and genuine completed TEAM + PLAYER_PROP slate validation. Production deployment, merge, recurring SHADOW, LIVE, and model promotion remain separately gated.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a truly least-privilege PostgreSQL login for append-only GENOME SHADOW observations without using the service role, changing production, or incurring costs before separate approvals.

**Architecture:** Keep canonical GENOME in one Supabase project, preserve the shared v0.3 pure evaluator and real freeze contract, but replace the unproven custom PostgREST/JWT writer with a direct TLS-verified PostgreSQL LOGIN. A narrow database gateway role owns carefully reviewed SHADOW functions, while the login has no direct table writes or canonical execution permissions. Initial work is a fail-closed config and offline tests only; permission proof and migrations are gated on an approved isolated database.

**Tech Stack:** Python 3.11, Python stdlib/pytest 8, PostgreSQL/Supabase, GitHub Actions. Runtime driver is pinned to `psycopg[binary]==3.3.5` after CI verification.

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
- `supabase/migrations/2026091602_shadow_experience.sql`: dependency-ordered restricted SHADOW migration, rehearsed only in disposable PostgreSQL so far; not applied to production.
- `goji/shadow_genome.py`: strict three-operation psycopg client; no SQL or RPC escape hatch.
- `goji/shadow.py`: runner reusing `evaluate_candidate`, `eligible_shadow_freeze` and pure report logic.
- `.github/workflows/goji-postgame.yml`, `scripts/goji_postgame.py`, `README.md`: manual AUDIT/SHADOW only, no cron, no LIVE, no service role in SHADOW job.

---

### Task 1: Stage safe direct-connection configuration and test locally/CI (no database)

**Status:** COMPLETE on feature branch.

### Task 2: Stage SQL permission contract and rehearse in disposable PostgreSQL

**Status:** COMPLETE for disposable PostgreSQL rehearsal. The real prerequisite migration plus SHADOW migration, restricted login, RLS/ACL boundary, replay/idempotency, correction revisions, append-only enforcement, TLS hostname checks, and canonical-state immutability all pass in GitHub Actions fixtures. This does not prove Supabase-hosted connectivity or platform behavior.

### Task 3: Restricted runner, manual workflow and release checks

**Status:** COMPLETE on feature branch. `ShadowGenome` exposes only readiness/queue/record, `ShadowPostgame` reuses the shared evaluator, CLI permits only AUDIT/SHADOW, SHADOW fails closed on its separate credential, workflow is manual-only with no LIVE or cron, and the runtime driver is pinned.

## Remaining acceptance gates

1. **Supabase-hosted isolated proof:** Create or use an explicitly approved isolated Supabase environment, apply the two migrations there, provision a test `goji_shadow_writer` credential outside source control, and prove TLS `verify-full`, role attributes/memberships, allowlisted SHADOW calls, denied canonical writes, RLS, replay/revision behavior, and cleanup. Do not incur a branch/project cost without separate approval.
2. **Genuine slate validation:** Run zero-write AUDIT and then separately approved SHADOW on a genuinely pregame-frozen completed slate containing both TEAM and PLAYER_PROP rows. Verify provider identity, exact player-prop score/line, proposed outcomes, ambiguity handling, replay/correction behavior, and no canonical mutations. Zero eligible rows means zero experience; do not backfill or fabricate.
3. **Production/release approvals:** Only after gates 1–2 pass: request explicit approval for recoverable production checkpoint, ordered migrations, production restricted credential/CA provisioning, initial controlled SHADOW writes, merge, and later recurring SHADOW. LIVE and maturity/model promotion remain separate future approvals.

## Verified checkpoint

Exact branch head `dde78a6ee77bcdc9812100c9a7dc53023d75586f` passed GitHub CI run `35169564693` and SHADOW database preflight run `35169564770`. Production inspection still shows zero `goji_shadow_writer`/`goji_shadow_gateway` roles, no `genome_shadow_observations` table, and no SHADOW RPCs.
