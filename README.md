# Goji

Goji is a sports prediction and learning system, evolved from the earlier Shin project. This repository is Goji's runnable Python integration/application layer; Supabase/GENOME remains the canonical durable state for frozen predictions, settlements, experience, and readiness.

## Current foundation

- SportsGameOdds event connectivity and normalization
- explicit provenance at the provider boundary
- CARAPACE pregame evidence validation with PASS / PASS_WITH_CAUTION / BLOCKED states
- PREYSCAN player-prop validation for player, market, line, side, participation, role/opportunity, and matchup context
- an operational full-slate preparation path that keeps predictions and blocked opportunities separate
- cold-start baseline outputs that never impersonate a trained model
- canonical GENOME RPC access for slate freezing, review queues, scoreboards, and wager links
- credential-free unit tests and CI

Goji's current prediction engine is still **COLD_START**. It returns `NO_ROAR` rather than pretending missing evidence is confidence, and it never substitutes sportsbook implied probability for Goji's own model probability.

## Operational pregame flow

The v0.2 pregame path is:

```text
ECHOSENSE -> CARAPACE -> PREYSCAN (PLAYER_PROP) -> CORTEX/ColdStartBaseline -> GENOME freeze
```

`goji.operational.OperationalPregame.prepare()` is intentionally write-free. It validates every candidate and returns a `PreparedSlate` containing two separate collections:

- `predictions`: opportunities that passed CARAPACE (and PREYSCAN for player props)
- `blocked`: opportunities rejected because identity, freshness, provenance, conflict, or prop requirements were not good enough

Only an explicit `OperationalPregame.freeze()` call writes the prepared slate through the existing `GenomeClient.freeze_slate()` RPC. This keeps review and freeze as separate steps and preserves GENOME as the only canonical persistence layer.

Default CARAPACE freshness policy is caution after 30 minutes, block after 90 minutes, with five minutes of positive clock-skew tolerance. These thresholds are configurable through `FreshnessPolicy`.

## Requirements

- Python 3.11
- `SPORTSGAMEODDS_API_KEY` for the optional live SportsGameOdds check
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for GENOME RPC access

Never commit credentials. Configure them through your local environment or GitHub Actions secrets.

## Setup

```bash
python -m pip install -r requirements.txt
python -m pytest -v
python scripts/goji_check.py
```

Optional live SportsGameOdds smoke check:

```bash
SPORTSGAMEODDS_API_KEY=... python scripts/goji_check.py --sgo
```

## Architecture boundary

GitHub code does not duplicate GENOME. Persistent prediction state and learning state stay in canonical Supabase functions. This repository calls those functions through `goji.genome.GenomeClient`.

The operational runner also does not turn validation into prediction intelligence. CARAPACE and PREYSCAN decide whether evidence is safe enough to freeze; the cold-start predictor remains a separate concern.

## Still ahead

A trained REACTOR model, automatic candidate construction from complete team/prop feeds, autonomous live-game monitoring, automatic settlement orchestration inside this repository, bankroll sizing, and the full SCARS -> MOLT -> Evidence Maturity postgame loop as Python application code are not part of v0.2.
