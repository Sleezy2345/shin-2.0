# Goji

Goji is a sports prediction and learning system, evolved from the earlier Shin project. This repository is Goji's runnable Python integration/application layer; Supabase/GENOME remains the canonical durable state for frozen predictions, settlements, postmortems, experience, and readiness.

## Current foundation

Goji v0.3 preserves the v0.2 pregame foundation and adds guarded postgame intelligence:

- SportsGameOdds event and finalized-result connectivity with provider provenance
- CARAPACE pregame validation with PASS / PASS_WITH_CAUTION / BLOCKED states
- PREYSCAN player-prop validation for player, market, line, side, participation, role/opportunity, and matchup context
- operational full-slate preparation that keeps predictions and blocked opportunities separate
- cold-start outputs that never impersonate a trained model
- postgame CARAPACE validation that distinguishes final from actually settleable
- sport-agnostic settlement orchestration with separate team and player-prop evaluators
- exact SportsGameOdds market-score grading for supported player props; missing/unsupported scoring never becomes zero
- manual `AUDIT` and isolated `SHADOW` release modes; CLI/workflow `LIVE` is intentionally unavailable
- retry-safe settlement, SCARS, and MOLT phases backed by canonical GENOME queues/RPCs for the separately gated canonical path
- SCARS expectation-error diagnosis that keeps outcome correctness separate from reasoning quality
- MOLT candidate hypotheses that remain OBSERVED / SHADOW and require human approval
- Evidence Maturity data remains multi-dimensional rather than one opaque score
- credential-free unit tests and Python 3.11 CI

Goji's current prediction engine is still **COLD_START**. It returns `NO_ROAR` rather than pretending missing evidence is confidence, and it never substitutes sportsbook implied probability for Goji's own model probability.

## Operational pregame flow

The v0.2+ pregame path remains:

```text
ECHOSENSE -> CARAPACE -> PREYSCAN (PLAYER_PROP) -> CORTEX/ColdStartBaseline -> GENOME freeze
```

`goji.operational.OperationalPregame.prepare()` is intentionally write-free. It validates every candidate and returns a `PreparedSlate` containing separate `predictions` and `blocked` collections. Only an explicit `OperationalPregame.freeze()` writes through the canonical `GenomeClient.freeze_slate()` RPC.

Default pregame CARAPACE freshness policy is caution after 30 minutes, block after 90 minutes, with five minutes of positive clock-skew tolerance. Those pregame thresholds are not reused for completed postgame results.

## Postgame flow

The v0.3 postgame evaluation path is:

```text
GENOME frozen queue
  -> ECHOSENSE / SportsGameOdds finalized result adapter
  -> postgame CARAPACE
  -> ResolvedOutcome
  -> TEAM or PLAYER_PROP settlement evaluator
  -> AUDIT proposal or isolated SHADOW observation
  -> SCARS diagnosis
  -> MOLT proposal
  -> Evidence Maturity gates
```

The postgame contract is sport-agnostic. MLB and CFB are the first live-validation targets; NFL and later sports should use the same contract after their result/stat fixtures pass the same safety gates.

### Final does not automatically mean settleable

A result must be finalized and match the frozen prediction identity. Team grading requires verified final scores. Player props require the exact frozen provider market identifier plus a supported final market score. Missing, conflicting, unsupported, or ambiguous evidence remains unresolved or becomes `REVIEW_REQUIRED`; Goji does not guess.

### AUDIT and SHADOW

`AUDIT` executes postgame decisions in memory and performs zero settlement, postmortem, hypothesis, evidence, or SHADOW writes. It is the default CLI mode.

`SHADOW` uses the same frozen-evidence contract and evaluator, but writes only through the dedicated restricted `goji_shadow_writer` PostgreSQL login to the isolated append-only SHADOW boundary. It does not call canonical settlement, training, official scoreboard, or promotion writers. SHADOW defaults off and requires an independent TLS-verified database connection.

`LIVE` canonical postgame settlement remains a separate future release gate and is deliberately unavailable from the initial v0.3 CLI and GitHub workflow.

Run zero-write AUDIT manually:

```bash
GOJI_POSTGAME_MODE=AUDIT python scripts/goji_postgame.py
```

Optionally scope it to one canonical slate:

```bash
GOJI_POSTGAME_MODE=AUDIT GOJI_SLATE_ID=slate-id python scripts/goji_postgame.py
```

The GitHub Actions postgame workflow is manual only. Dispatch exposes `AUDIT` or `SHADOW`; there is no cron schedule and no `LIVE` option.

### Restricted SHADOW runtime

SHADOW requires all of the following:

- `GOJI_SHADOW_ENABLED=true`
- `GOJI_SHADOW_DATABASE_URL` for the exact `goji_shadow_writer` login
- `sslmode=verify-full` in that URI
- an absolute `sslrootcert` path in that URI
- `SPORTSGAMEODDS_API_KEY`

The GitHub SHADOW job accepts the database CA certificate separately as `GOJI_SHADOW_CA_CERT` and materializes it at `/tmp/goji-supabase-ca.crt`; the database URL must reference that absolute path. The SHADOW runtime never falls back to `SUPABASE_SERVICE_ROLE_KEY`.

## Learning safety

Settlement answers **what happened**. SCARS asks **what it meant**. MOLT asks whether there is a recurring candidate lesson.

SCARS only scores expectation quality where frozen expectations can be compared with observed evidence. A win is not automatically good reasoning, and a loss is not automatically a model miss. Data issues and unexpected events receive low learning value and are not treated as clean pattern evidence.

MOLT does not alter REACTOR, SPINES, THERMAL, ROAR, calibration, or any other production behavior. It can propose OBSERVED/SHADOW evidence only. Promotion remains outside this runner and continues to require Evidence Maturity, RIVAL/ARENA/FOSSIL review, and human approval.

## GENOME boundary

GitHub code does not duplicate GENOME. Persistent prediction and learning state stay in canonical Supabase structures. v0.3 stages `supabase/migrations/2026091601_postgame_intelligence.sql` plus `supabase/migrations/2026091602_shadow_experience.sql`. The second migration creates the restricted SHADOW roles, RLS boundary, append-only observation table, and three allowlisted SHADOW functions.

Both migrations have a disposable PostgreSQL rehearsal in CI, including restricted-login permission denials, replay/idempotency, correction revision behavior, TLS hostname verification, and canonical-state immutability against fixtures. This is **not** proof of the Supabase-hosted environment.

Production migrations, credentials, initial controlled SHADOW writes, merge, recurring execution, LIVE mode, and model/maturity promotion require separate approval.

## Requirements

- Python 3.11
- `SPORTSGAMEODDS_API_KEY` for SportsGameOdds access
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` only for canonical AUDIT/GENOME read paths that already require them
- `psycopg[binary]==3.3.5` for the dedicated SHADOW PostgreSQL client

Never commit credentials. Configure them through the environment or GitHub Actions secrets.

## Setup and verification

```bash
python -m pip install -r requirements.txt
python -m pytest -v
python scripts/goji_check.py
```

Optional live SportsGameOdds connectivity check:

```bash
SPORTSGAMEODDS_API_KEY=... python scripts/goji_check.py --sgo
```

## Still ahead

Goji v0.3 does **not** claim to have a trained REACTOR model. Before merge/deployment, the staged restricted migration/client must still be proven against an explicitly approved isolated Supabase-hosted environment and a genuine completed TEAM + PLAYER_PROP slate must match independent ground truth. Production deployment, recurring SHADOW, LIVE settlement, bankroll sizing, autonomous pregame slate generation, and evidence-backed model changes remain separately gated.
