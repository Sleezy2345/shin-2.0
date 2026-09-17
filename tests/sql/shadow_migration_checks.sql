-- Run ONLY on disposable PostgreSQL over TCP as actual restricted login.
\set ON_ERROR_STOP on
DO $$
DECLARE
  v_first jsonb;
  v_retry jsonb;
  v_revision jsonb;
  v_payload jsonb;
BEGIN
  IF session_user <> 'goji_shadow_writer' OR current_user <> 'goji_shadow_writer' THEN
    RAISE EXCEPTION 'migration checks not run as the restricted LOGIN';
  END IF;
  IF (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication FROM pg_roles
      WHERE rolname='goji_shadow_writer') THEN
    RAISE EXCEPTION 'restricted login has elevated privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
             WHERE r.rolname='goji_shadow_writer') THEN
    RAISE EXCEPTION 'restricted login unexpectedly belongs to another role';
  END IF;
  IF public.genome_shadow_ready()->>'ready' <> 'true' THEN
    RAISE EXCEPTION 'readiness RPC failed';
  END IF;
  IF (SELECT count(*) FROM public.genome_shadow_queue('shadow-fixture')) <> 2 THEN
    RAISE EXCEPTION 'queue did not restrict to genuine pregame team and prop freezes';
  END IF;
  v_payload := jsonb_build_object(
    'freeze_fingerprint','fp-team','slate_id','shadow-fixture',
    'evaluator_version','team/0.3','adapter_version','sgo/0.3',
    'carapace',jsonb_build_object('decision','PASS'),
    'result',jsonb_build_object('provider','sportsgameodds','provider_event_id','event-1',
      'source_id','event-1','sport','MLB','finalized',true,
      'observed_at','2026-09-16T00:00:00Z','home_score',3,'away_score',1),
    'grade',jsonb_build_object('status','PROPOSED_SETTLEMENT','outcome','WIN',
      'grading_inputs',jsonb_build_object('home_score',3,'away_score',1))
  );
  v_first := public.genome_shadow_record('team-eligible',v_payload);
  IF v_first->>'created'<>'true' OR v_first->>'learning_eligible'<>'false' THEN
    RAISE EXCEPTION 'first record did not append safely';
  END IF;
  v_retry:=public.genome_shadow_record('team-eligible',v_payload);
  IF v_retry->>'created'<>'false' OR v_retry->>'observation_id'<>v_first->>'observation_id' THEN
    RAISE EXCEPTION 'exact replay created another observation';
  END IF;
  -- Retrieval-time-only metadata must not manufacture a second observation.
  v_retry:=public.genome_shadow_record('team-eligible',
    jsonb_set(v_payload,'{result,observed_at}','"2026-09-17T00:00:00Z"'));
  IF v_retry->>'created'<>'false' THEN
    RAISE EXCEPTION 'fetch timestamp created duplicate experience';
  END IF;
  v_revision:=public.genome_shadow_record('team-eligible',
    jsonb_set(v_payload,'{result,home_score}','4'));
  IF v_revision->>'created'<>'true' OR v_revision->>'revision_of'<>v_first->>'observation_id' THEN
    RAISE EXCEPTION 'changed result did not append a linked correction';
  END IF;
  BEGIN
    PERFORM public.genome_shadow_record('test-ineligible',v_payload);
    RAISE EXCEPTION 'TEST freeze was accepted';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM = 'TEST freeze was accepted' THEN RAISE; END IF;
  END;
  BEGIN
    PERFORM public.genome_shadow_record('team-eligible',v_payload - 'carapace');
    RAISE EXCEPTION 'unverified evidence was accepted';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM = 'unverified evidence was accepted' THEN RAISE; END IF;
  END;
  BEGIN EXECUTE 'SELECT * FROM public.shin2_verdicts LIMIT 1';
    RAISE EXCEPTION 'direct verdict SELECT allowed';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN EXECUTE 'INSERT INTO public.shin2_settlements VALUES (''illegal'',''team-eligible'',''{}'',1)';
    RAISE EXCEPTION 'canonical settlement INSERT allowed';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN EXECUTE 'SELECT * FROM public.genome_shadow_observations LIMIT 1';
    RAISE EXCEPTION 'direct SHADOW table SELECT allowed';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN EXECUTE 'DELETE FROM public.genome_shadow_observations';
    RAISE EXCEPTION 'SHADOW DELETE allowed';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN EXECUTE 'SELECT public.genome_settle(''illegal'',''team-eligible'',''{}''::jsonb,''fp-team'')';
    RAISE EXCEPTION 'canonical genome_settle allowed';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN EXECUTE 'SELECT public.genome_freeze_slate(''bad'',''[]''::jsonb,''[]''::jsonb)';
    RAISE EXCEPTION 'canonical genome_freeze_slate allowed';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN EXECUTE 'SET ROLE postgres'; RAISE EXCEPTION 'role escalation allowed';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
