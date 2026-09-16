-- Executed over TCP as the actual goji_shadow_writer LOGIN, not SET ROLE impersonation.
\set ON_ERROR_STOP on
DO $$
BEGIN
 IF session_user <> 'goji_shadow_writer' OR current_user <> 'goji_shadow_writer' THEN
  RAISE EXCEPTION 'proof was not executed as restricted login';
 END IF;
 IF (SELECT rolbypassrls OR rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication
     FROM pg_catalog.pg_roles WHERE rolname = session_user) THEN
  RAISE EXCEPTION 'restricted role has unexpected privileges';
 END IF;
 IF (SELECT count(*) FROM pg_catalog.pg_auth_members m
     JOIN pg_catalog.pg_roles r ON r.oid=m.member
     WHERE r.rolname='goji_shadow_writer') <> 0 THEN
  RAISE EXCEPTION 'restricted writer has role memberships';
 END IF;
 IF (SELECT public.genome_shadow_ready()) <> 1 THEN
  RAISE EXCEPTION 'narrow readiness function could not read eligible freeze';
 END IF;
 IF (SELECT public.genome_shadow_record('genuine-1','fp1')) <> 1 THEN
  RAISE EXCEPTION 'authorized shadow observation failed';
 END IF;
 IF (SELECT public.genome_shadow_record('genuine-1','fp1')) <> 1 THEN
  RAISE EXCEPTION 'idempotent retry failed';
 END IF;
 BEGIN
  PERFORM public.genome_shadow_record('test-1','fp2');
  RAISE EXCEPTION 'TEST freeze was accepted';
 EXCEPTION WHEN raise_exception THEN
  IF SQLERRM <> 'not an eligible frozen verdict' THEN RAISE; END IF;
 END;
 BEGIN
  EXECUTE 'SELECT 1 FROM public.shin2_verdicts LIMIT 1';
  RAISE EXCEPTION 'direct verdict SELECT unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'INSERT INTO public.shin2_verdicts VALUES (''bad'', ''{}'', ''fp'', 1)';
  RAISE EXCEPTION 'direct verdict INSERT unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'UPDATE public.shin2_verdicts SET freeze_fingerprint = ''bad''';
  RAISE EXCEPTION 'direct verdict UPDATE unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'DELETE FROM public.shin2_verdicts';
  RAISE EXCEPTION 'direct verdict DELETE unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'SELECT 1 FROM public.shin2_settlements LIMIT 1';
  RAISE EXCEPTION 'direct settlement SELECT unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'INSERT INTO public.shin2_settlements VALUES (''bad'', ''genuine-1'', ''{}'', 1)';
  RAISE EXCEPTION 'direct settlement INSERT unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'SELECT * FROM public.genome_shadow_observations';
  RAISE EXCEPTION 'direct shadow observation SELECT unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'DELETE FROM public.genome_shadow_observations';
  RAISE EXCEPTION 'direct shadow observation DELETE unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'SELECT public.genome_settle(''settlement-1'',''genuine-1'',''{}''::jsonb,''fp1'')';
  RAISE EXCEPTION 'canonical settlement function unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'SELECT public.genome_freeze_slate(''slate'',''[]''::jsonb,''[]''::jsonb)';
  RAISE EXCEPTION 'canonical freeze function unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'SET ROLE postgres';
  RAISE EXCEPTION 'SET ROLE postgres unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'CREATE TABLE public.shadow_forbidden (id integer)';
  RAISE EXCEPTION 'schema CREATE unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  EXECUTE 'CREATE TEMP TABLE shadow_forbidden_temp (id integer)';
  RAISE EXCEPTION 'TEMP privilege unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END;
$$;
