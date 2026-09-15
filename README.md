# Goji

Goji is a sports prediction and learning system, evolved from the earlier Shin project. This repository is Goji's runnable Python integration/application layer; Supabase/GENOME remains the canonical durable state for frozen predictions, settlements, experience, and readiness.

## Current foundation

- SportsGameOdds event connectivity and normalization
- explicit provenance at the provider boundary
- cold-start baseline outputs that never impersonate a trained model
- canonical GENOME RPC access for slate freezing, review queues, scoreboards, and wager links
- credential-free unit tests and CI

Goji's first-slice baseline is **COLD_START**. It returns `NO_ROAR` when evidence is insufficient and never substitutes sportsbook implied probability for Goji's own model probability.

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

## Not implemented in this foundation

A trained REACTOR model, autonomous live-game monitoring, autonomous settlement scheduling, bankroll sizing, a web UI, and every Concept Lab subsystem as Python code are intentionally outside this first slice.
