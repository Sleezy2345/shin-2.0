-- GOJI v0.3 SHADOW: REVIEW/STAGING ONLY. DO NOT APPLY TO PRODUCTION WITHOUT APPROVAL.
-- Depends on 2026091601_postgame_intelligence.sql; provision login credentials separately.
BEGIN;
DO $$ BEGIN
  IF to_regclass('public.genome_postgame_reviews') IS NULL OR
     to_regprocedure('public.genome_postmortem_queue(text)') IS NULL THEN
    RAISE EXCEPTION 'SHADOW requires the postgame-intelligence migration first';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('goji_shadow_writer','goji_shadow_gateway')) THEN
    RAISE EXCEPTION 'SHADOW roles already exist; manual review required';
  END IF;
END $$;

CREATE ROLE goji_shadow_writer LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE goji_shadow_gateway NOLOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
-- PostgreSQL 17 requires SET ROLE membership and target CREATE on schema to transfer
-- function ownership as a non-superuser. Both are transaction-scoped then revoked.
DO $$ BEGIN
  EXECUTE pg_catalog.format('GRANT goji_shadow_gateway TO %I WITH SET TRUE', current_user);
END $$;
GRANT USAGE, CREATE ON SCHEMA public TO goji_shadow_gateway;
GRANT USAGE ON SCHEMA public TO goji_shadow_writer;
GRANT SELECT ON public.shin2_verdicts TO goji_shadow_gateway;
-- Canonical RLS remains enabled; only the non-bypass gateway can see genuine pregame rows.
CREATE POLICY goji_shadow_frozen_read ON public.shin2_verdicts
FOR SELECT TO goji_shadow_gateway USING (
  CASE WHEN (payload->>'record_kind' = 'PREDICTION' OR payload->>'capture_mode' = 'FULL_SLATE')
    AND payload->>'prediction_type' IN ('TEAM','PLAYER_PROP')
    AND jsonb_typeof(payload->'game_start_at') = 'number'
    AND payload->'inputs'->>'provider_event_id' IS NOT NULL
    AND length(btrim(payload->'inputs'->>'provider_event_id')) > 0
  THEN logged_at < (payload->>'game_start_at')::double precision
  ELSE false END
);

CREATE TABLE public.genome_shadow_observations (
  observation_id text PRIMARY KEY,
  prediction_id text NOT NULL REFERENCES public.shin2_verdicts(prediction_id),
  freeze_fingerprint text NOT NULL,
  evaluator_version text NOT NULL,
  result_digest text NOT NULL,
  revision_of text REFERENCES public.genome_shadow_observations(observation_id),
  lifecycle text NOT NULL CHECK (lifecycle IN ('OBSERVED','CORRECTION_REVIEW')),
  learning_eligible boolean NOT NULL DEFAULT false CHECK (learning_eligible = false),
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (prediction_id, freeze_fingerprint, evaluator_version, result_digest)
);
ALTER TABLE public.genome_shadow_observations ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT ON public.genome_shadow_observations TO goji_shadow_gateway;
CREATE POLICY goji_shadow_observation_read ON public.genome_shadow_observations
FOR SELECT TO goji_shadow_gateway USING (true);
CREATE POLICY goji_shadow_observation_append ON public.genome_shadow_observations
FOR INSERT TO goji_shadow_gateway WITH CHECK (
  learning_eligible = false AND lifecycle IN ('OBSERVED','CORRECTION_REVIEW')
);

CREATE FUNCTION public.genome_shadow_deny_mutation() RETURNS trigger LANGUAGE plpgsql
SET search_path = '' AS $$ BEGIN
  RAISE EXCEPTION 'SHADOW observations are append-only' USING ERRCODE='42501';
END $$;
REVOKE ALL ON FUNCTION public.genome_shadow_deny_mutation() FROM PUBLIC, anon, authenticated, service_role;
CREATE TRIGGER genome_shadow_deny_mutation BEFORE UPDATE OR DELETE ON public.genome_shadow_observations
FOR EACH ROW EXECUTE FUNCTION public.genome_shadow_deny_mutation();

-- SECURITY DEFINER ownership is transferred to a dedicated non-bypass role.
CREATE FUNCTION public.genome_shadow_ready() RETURNS jsonb LANGUAGE sql STABLE
SECURITY DEFINER SET search_path = '' AS $$
  SELECT pg_catalog.jsonb_build_object('schema','SHADOW/0.3','ready',true);
$$;
ALTER FUNCTION public.genome_shadow_ready() OWNER TO goji_shadow_gateway;
REVOKE ALL ON FUNCTION public.genome_shadow_ready() FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.genome_shadow_ready() TO goji_shadow_writer;

CREATE FUNCTION public.genome_shadow_queue(p_slate_id text DEFAULT NULL)
RETURNS TABLE(prediction_id text, slate_id text, sport text, prediction_type text,
  selection text, freeze_fingerprint text, frozen_at timestamptz, payload jsonb)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT v.prediction_id, v.payload->>'slate_id', v.payload->>'sport',
    v.payload->>'prediction_type', v.payload->>'selection',v.freeze_fingerprint,
    pg_catalog.to_timestamp(v.logged_at),v.payload
  FROM public.shin2_verdicts v
  WHERE (v.payload->>'record_kind'='PREDICTION' OR v.payload->>'capture_mode'='FULL_SLATE')
    AND v.payload->>'prediction_type' IN ('TEAM','PLAYER_PROP')
    AND v.payload->>'sport' IN ('MLB','CFB')
    AND length(btrim(coalesce(v.payload->>'selection',''))) > 0
    AND length(btrim(coalesce(v.payload->>'slate_id',''))) > 0
    AND jsonb_typeof(v.payload->'game_start_at') = 'number'
    AND length(btrim(coalesce(v.payload->'inputs'->>'provider_event_id',''))) > 0
    AND (p_slate_id IS NULL OR v.payload->>'slate_id'=p_slate_id)
  ORDER BY v.prediction_id;
$$;
ALTER FUNCTION public.genome_shadow_queue(text) OWNER TO goji_shadow_gateway;
REVOKE ALL ON FUNCTION public.genome_shadow_queue(text) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.genome_shadow_queue(text) TO goji_shadow_writer;

CREATE FUNCTION public.genome_shadow_record(p_prediction_id text,p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
  v_verdict public.shin2_verdicts%ROWTYPE;
  v_observation public.genome_shadow_observations%ROWTYPE;
  v_previous text;
  v_version text;
  v_digest text;
  v_id text;
  v_result jsonb;
  v_grade jsonb;
BEGIN
  IF p_prediction_id IS NULL OR btrim(p_prediction_id)='' OR
     p_payload IS NULL OR jsonb_typeof(p_payload)<>'object' THEN
    RAISE EXCEPTION 'invalid SHADOW observation';
  END IF;
  PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('shadow:' || p_prediction_id,0));
  SELECT * INTO v_verdict FROM public.shin2_verdicts WHERE prediction_id=p_prediction_id;
  IF NOT FOUND OR p_payload->>'freeze_fingerprint' IS DISTINCT FROM v_verdict.freeze_fingerprint
     OR p_payload->>'slate_id' IS DISTINCT FROM v_verdict.payload->>'slate_id'
     OR v_verdict.payload->>'prediction_type' NOT IN ('TEAM','PLAYER_PROP') THEN
    RAISE EXCEPTION 'missing eligible canonical frozen prediction';
  END IF;
  v_result:=p_payload->'result'; v_grade:=p_payload->'grade';
  v_version:=nullif(p_payload->>'evaluator_version','');
  IF v_version IS NULL OR jsonb_typeof(v_result)<>'object' OR
     jsonb_typeof(v_grade)<>'object' OR
     p_payload->'carapace'->>'decision' IS DISTINCT FROM 'PASS' OR
     nullif(p_payload->>'adapter_version','') IS NULL OR
     v_result->>'provider' IS DISTINCT FROM 'sportsgameodds' OR
     v_result->>'source_id' IS DISTINCT FROM v_verdict.payload->'inputs'->>'provider_event_id' OR
     v_result->>'provider_event_id' IS DISTINCT FROM v_verdict.payload->'inputs'->>'provider_event_id' OR
     v_result->>'sport' IS DISTINCT FROM v_verdict.payload->>'sport' OR
     v_result->>'finalized' IS DISTINCT FROM 'true' OR
     nullif(v_result->>'observed_at','') IS NULL OR
     v_grade->>'status' IS DISTINCT FROM 'PROPOSED_SETTLEMENT' OR
     v_grade->>'outcome' IS NULL OR
     v_grade->>'outcome' NOT IN ('WIN','LOSS','PUSH','VOID') THEN
    RAISE EXCEPTION 'missing verified SHADOW evidence';
  END IF;
  -- The digest excludes fetch-only timestamps. A corrected result/grade appends a revision.
  v_digest:=pg_catalog.md5((v_result - 'observed_at' - 'retrieved_at')::text || v_grade::text);
  v_id:=pg_catalog.md5(p_prediction_id || ':' || v_verdict.freeze_fingerprint || ':' || v_version || ':' || v_digest);
  SELECT * INTO v_observation FROM public.genome_shadow_observations
   WHERE prediction_id=p_prediction_id AND freeze_fingerprint=v_verdict.freeze_fingerprint
    AND evaluator_version=v_version AND result_digest=v_digest;
  IF FOUND THEN
    RETURN pg_catalog.jsonb_build_object('created',false,'observation_id',v_observation.observation_id,
      'revision_of',v_observation.revision_of,'learning_eligible',false);
  END IF;
  SELECT observation_id INTO v_previous FROM public.genome_shadow_observations
   WHERE prediction_id=p_prediction_id ORDER BY created_at DESC,observation_id DESC LIMIT 1;
  INSERT INTO public.genome_shadow_observations
    (observation_id,prediction_id,freeze_fingerprint,evaluator_version,result_digest,revision_of,lifecycle,payload)
  VALUES (v_id,p_prediction_id,v_verdict.freeze_fingerprint,v_version,v_digest,v_previous,
    CASE WHEN v_previous IS NULL THEN 'OBSERVED' ELSE 'CORRECTION_REVIEW' END,p_payload)
  RETURNING * INTO v_observation;
  RETURN pg_catalog.jsonb_build_object('created',true,'observation_id',v_observation.observation_id,
    'revision_of',v_observation.revision_of,'learning_eligible',false);
END $$;
ALTER FUNCTION public.genome_shadow_record(text,jsonb) OWNER TO goji_shadow_gateway;
REVOKE ALL ON FUNCTION public.genome_shadow_record(text,jsonb) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.genome_shadow_record(text,jsonb) TO goji_shadow_writer;
-- Remove ownership-transfer privileges before committing: gateway has no schema CREATE.
REVOKE CREATE ON SCHEMA public FROM goji_shadow_gateway;
DO $$ BEGIN
  EXECUTE pg_catalog.format('REVOKE goji_shadow_gateway FROM %I', current_user);
END $$;
COMMIT;
