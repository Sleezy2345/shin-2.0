-- Test-only minimal baseline derived from read-only GENOME catalog inspection.
-- Never apply to a Supabase project; it intentionally replaces none of its actual schema.
\set ON_ERROR_STOP on
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE public.shin2_verdicts (
 prediction_id text PRIMARY KEY, payload jsonb NOT NULL,
 freeze_fingerprint text NOT NULL, logged_at double precision NOT NULL
);
CREATE TABLE public.shin2_settlements (
 settlement_id text PRIMARY KEY, prediction_id text NOT NULL UNIQUE REFERENCES public.shin2_verdicts,
 payload jsonb NOT NULL, logged_at double precision NOT NULL
);
ALTER TABLE public.shin2_verdicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shin2_settlements ENABLE ROW LEVEL SECURITY;
CREATE TABLE public.genome_experience_events (
 experience_id text PRIMARY KEY, prediction_id text NOT NULL REFERENCES public.shin2_verdicts
);
ALTER TABLE public.genome_experience_events ENABLE ROW LEVEL SECURITY;
CREATE TABLE public.prediction_postmortems (
 memory_id text PRIMARY KEY, prediction_id text NOT NULL UNIQUE REFERENCES public.shin2_verdicts,
 game_id text, sport text NOT NULL, lifecycle_state text NOT NULL DEFAULT 'RESOLVED',
 expected_state jsonb NOT NULL DEFAULT '{}', actual_state jsonb NOT NULL DEFAULT '{}',
 deltas jsonb NOT NULL DEFAULT '{}', primary_failure text,
 secondary_factors jsonb NOT NULL DEFAULT '[]', data_quality jsonb NOT NULL DEFAULT '{}',
 confidence_assessment jsonb NOT NULL DEFAULT '{}', calibration_assessment jsonb NOT NULL DEFAULT '{}',
 segment jsonb NOT NULL DEFAULT '{}', evidence jsonb NOT NULL DEFAULT '{}',
 provenance jsonb NOT NULL DEFAULT '[]', causal_confidence double precision,
 correction_hypothesis jsonb NOT NULL DEFAULT '{}', evolve_action jsonb NOT NULL DEFAULT '{}',
 schema_version text NOT NULL DEFAULT '1.0', created_at timestamptz NOT NULL DEFAULT now(),
 expectation_quality text, reasoning_quality text, outcome_informativeness text, variance_class text,
 learning_value double precision, eligible_for_pattern_learning boolean NOT NULL DEFAULT false,
 learning_notes jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE public.genome_experience_hypotheses (
 hypothesis_id text PRIMARY KEY, sport text NOT NULL, prediction_type text NOT NULL,
 segment_key text NOT NULL, hypothesis text NOT NULL, scope jsonb NOT NULL DEFAULT '{}',
 lifecycle_status text NOT NULL DEFAULT 'OBSERVED', deployment_status text NOT NULL DEFAULT 'SHADOW',
 predictive_evidence_status text NOT NULL DEFAULT 'UNPROVEN',
 causal_claim_status text NOT NULL DEFAULT 'UNPROVEN',human_approval_required boolean NOT NULL DEFAULT true,
 CONSTRAINT genome_experience_hypotheses_lifecycle_status_check
 CHECK (lifecycle_status IN ('OBSERVED','CANDIDATE','MATURE'))
);
CREATE TABLE public.genome_experience_evidence (
 evidence_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 hypothesis_id text NOT NULL REFERENCES public.genome_experience_hypotheses,
 prediction_id text REFERENCES public.shin2_verdicts,
 postmortem_memory_id text REFERENCES public.prediction_postmortems,
 evidence_family text NOT NULL,evidence_direction text NOT NULL,
 learning_value double precision, independent_group_key text,
 context jsonb NOT NULL DEFAULT '{}',notes jsonb NOT NULL DEFAULT '{}',
 observed_at timestamptz NOT NULL DEFAULT now()
);
CREATE FUNCTION public.genome_settle(text,text,jsonb,text) RETURNS jsonb
 LANGUAGE sql AS $$ SELECT '{}'::jsonb $$;
CREATE FUNCTION public.genome_freeze_slate(text,jsonb,jsonb) RETURNS jsonb
 LANGUAGE sql AS $$ SELECT '{}'::jsonb $$;
REVOKE ALL ON FUNCTION public.genome_settle(text,text,jsonb,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.genome_freeze_slate(text,jsonb,jsonb) FROM PUBLIC;
INSERT INTO public.shin2_verdicts(prediction_id,payload,freeze_fingerprint,logged_at) VALUES
 ('team-eligible','{"record_kind":"PREDICTION","capture_mode":"FULL_SLATE","slate_id":"shadow-fixture","sport":"MLB","game_id":"MLB-fixture","prediction_type":"TEAM","selection":"Home","game_start_at":1780000000,"inputs":{"provider_event_id":"event-1","home_team":"Home","away_team":"Away"}}','fp-team',1779999000),
 ('prop-eligible','{"record_kind":"PREDICTION","capture_mode":"FULL_SLATE","slate_id":"shadow-fixture","sport":"MLB","game_id":"MLB-fixture","prediction_type":"PLAYER_PROP","selection":"Player Over 1.5","game_start_at":1780000000,"inputs":{"provider_event_id":"event-1","player":"Player","market":"hits","provider_odd_id":"odd-1","line":1.5,"side":"OVER"}}','fp-prop',1779999000),
 ('test-ineligible','{"record_kind":"TEST","slate_id":"shadow-fixture","sport":"MLB","prediction_type":"TEAM","selection":"Away","game_start_at":1780000000,"inputs":{"provider_event_id":"event-1"}}','fp-test',1779999000);
-- Supabase's actual postgres project role is not superuser. Match that limitation.
ALTER ROLE postgres NOSUPERUSER CREATEROLE BYPASSRLS;
