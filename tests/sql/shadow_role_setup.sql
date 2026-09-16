-- Disposable PostgreSQL 17 permission-model rehearsal only. NOT a GENOME migration.
-- This simulates a minimal subset of the real Supabase schema. Never run on production.
\set ON_ERROR_STOP on

CREATE ROLE goji_shadow_writer LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER ROLE goji_shadow_writer PASSWORD :'shadow_password';
CREATE ROLE goji_shadow_gateway NOLOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE postgres FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO goji_shadow_writer, goji_shadow_gateway;

CREATE TABLE public.shin2_verdicts (
  prediction_id text PRIMARY KEY,
  payload jsonb NOT NULL,
  freeze_fingerprint text NOT NULL,
  logged_at double precision NOT NULL
);
CREATE TABLE public.shin2_settlements (
  settlement_id text PRIMARY KEY,
  prediction_id text NOT NULL,
  payload jsonb NOT NULL,
  logged_at double precision NOT NULL
);
ALTER TABLE public.shin2_verdicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shin2_settlements ENABLE ROW LEVEL SECURITY;
INSERT INTO public.shin2_verdicts VALUES
 ('genuine-1', '{"record_kind":"PREDICTION","game_start_at":1780000000}', 'fp1', 1779999000),
 ('test-1', '{"record_kind":"TEST","game_start_at":1780000000}', 'fp2', 1779999000);

-- Narrow dedicated function owner can only read genuinely frozen rows.
GRANT SELECT ON public.shin2_verdicts TO goji_shadow_gateway;
CREATE POLICY shadow_gateway_eligible_verdict ON public.shin2_verdicts
  FOR SELECT TO goji_shadow_gateway
  USING (payload->>'record_kind' = 'PREDICTION'
         AND payload ? 'game_start_at'
         AND logged_at < (payload->>'game_start_at')::double precision);

CREATE TABLE public.genome_shadow_observations (
  prediction_id text NOT NULL REFERENCES public.shin2_verdicts(prediction_id),
  freeze_fingerprint text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (prediction_id,freeze_fingerprint)
);
ALTER TABLE public.genome_shadow_observations ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT ON public.genome_shadow_observations TO goji_shadow_gateway;
CREATE POLICY shadow_gateway_observation_read ON public.genome_shadow_observations
  FOR SELECT TO goji_shadow_gateway USING (true);
CREATE POLICY shadow_gateway_observation_append ON public.genome_shadow_observations
  FOR INSERT TO goji_shadow_gateway WITH CHECK (true);

-- Canonical API signatures mirror the actual Supabase functions; never grant them to SHADOW.
CREATE FUNCTION public.genome_settle(p_settlement_id text,p_prediction_id text,p_payload jsonb,p_freeze_fingerprint text)
RETURNS text LANGUAGE sql AS $$ SELECT 'FORBIDDEN'::text $$;
CREATE FUNCTION public.genome_freeze_slate(p_slate_id text,p_predictions jsonb,p_blocked jsonb)
RETURNS text LANGUAGE sql AS $$ SELECT 'FORBIDDEN'::text $$;
REVOKE ALL ON FUNCTION public.genome_settle(text,text,jsonb,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.genome_freeze_slate(text,jsonb,jsonb) FROM PUBLIC;

-- These are deliberately simple fixtures: a permission probe, not final SHADOW business logic.
CREATE FUNCTION public.genome_shadow_ready() RETURNS integer
LANGUAGE sql SECURITY DEFINER SET search_path = ''
AS $$ SELECT count(*)::integer FROM public.shin2_verdicts $$;
ALTER FUNCTION public.genome_shadow_ready() OWNER TO goji_shadow_gateway;
REVOKE ALL ON FUNCTION public.genome_shadow_ready() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.genome_shadow_ready() TO goji_shadow_writer;

CREATE FUNCTION public.genome_shadow_record(p_prediction_id text,p_fingerprint text)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM public.shin2_verdicts
  WHERE prediction_id = p_prediction_id AND freeze_fingerprint = p_fingerprint
 ) THEN
  RAISE EXCEPTION 'not an eligible frozen verdict';
 END IF;
 INSERT INTO public.genome_shadow_observations(prediction_id, freeze_fingerprint)
 VALUES (p_prediction_id,p_fingerprint)
 ON CONFLICT (prediction_id,freeze_fingerprint) DO NOTHING;
 RETURN 1;
END;
$$;
ALTER FUNCTION public.genome_shadow_record(text,text) OWNER TO goji_shadow_gateway;
REVOKE ALL ON FUNCTION public.genome_shadow_record(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.genome_shadow_record(text,text) TO goji_shadow_writer;
