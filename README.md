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
- AUDIT and LIVE postgame modes, with AUDIT as the safe default
- retry-safe settlement, SCARS, and MOLT phases backed by canonical GENOME queues/RPCs
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

The v0.3 postgame path is:

```text
GENOME unresolved queue
  -> ECHOSENSE / SportsGameOdds finalized result adapter
  -> postgame CARAPACE
  -> ResolvedOutcome
  -> TEAM or PLAYER_PROP settlement evaluator
  -> AUDIT proposal or canonical GENOME settlement
  -> GENOME experience event
  -> SCARS diagnosis
  -> MOLT candidate/evidence
  -> Evidence Maturity
```

The postgame contract is sport-agnostic. MLB and CFB are the first live-validation targets; NFL and later sports should use the same contract after their result/stat fixtures pass the same safety gates.

### Final does not automatically mean settleable

A result must be finalized and match the frozen prediction identity. Team grading requires verified final scores. Player props require the exact frozen provider market identifier plus a supported final market score. Missing, conflicting, unsupported, or ambiguous evidence remains unresolved or becomes `REVIEW_REQUIRED`; Goji does not guess.

### AUDIT versus LIVE

`AUDIT` executes the postgame decisions in memory and performs zero settlement, postmortem, hypothesis, or evidence writes. It is the default CLI and scheduled-workflow mode.

`LIVE` uses the same validation and grading decisions but may write through canonical GENOME RPCs. LIVE is a release gate, not the default: the database migration must be applied and a completed real slate must match manual reality in AUDIT before LIVE should be enabled.

Run the postgame worker manually:

```bash
GOJI_POSTGAME_MODE=AUDIT python scripts/goji_postgame.py
```

Optionally scope it to one canonical slate:

```bash
GOJI_POSTGAME_MODE=AUDIT GOJI_SLATE_ID=slate-id python scripts/goji_postgame.py
```

The GitHub Actions postgame workflow runs hourly at minute 17 in AUDIT mode. Manual dispatch exposes AUDIT or LIVE, but LIVE should not be used until the v0.3 release gates are satisfied.

## Learning safety

Settlement answers **what happened**. SCARS asks **what it meant**. MOLT asks whether there is a recurring candidate lesson.

SCARS only scores expectation quality where frozen expectations can be compared with observed evidence. A win is not automatically good reasoning, and a loss is not automatically a model miss. Data issues and unexpected events receive low learning value and are not treated as clean pattern evidence.

MOLT does not alter REACTOR, SPINES, THERMAL, ROAR, calibration, or any other production behavior. It can create an OBSERVED/SHADOW hypothesis and attach evidence. Promotion remains outside this runner and continues to require Evidence Maturity, RIVAL/ARENA/FOSSIL review, and human approval.

## GENOME boundary

GitHub code does not duplicate GENOME. Persistent prediction and learning state stay in canonical Supabase structures. v0.3 ships `supabase/migrations/2026091601_postgame_intelligence.sql` to add the minimal postgame review registry and retry-safe RPC queues required by the runner while preserving the existing settlement, experience-event, postmortem, hypothesis, and evidence stores.

The migration must be reviewed/applied separately. Merely having the migration file in the repository does not mean production GENOME has been changed.

## Requirements

- Python 3.11
- `SPORTSGAMEODDS_API_KEY` for SportsGameOdds access
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for GENOME RPC access

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

Goji v0.3 does **not** claim to have a trained REACTOR model. Automatic construction of complete prediction candidates from live team/prop feeds is still ahead, as are full autonomous pregame slate generation, broader sport/market adapters, production LIVE-postgame graduation, bankroll sizing, and evidence-backed model changes promoted through the maturity process.
