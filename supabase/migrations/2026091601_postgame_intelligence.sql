begin;

create table if not exists public.genome_postgame_reviews (
  prediction_id text primary key references public.shin2_verdicts(prediction_id),
  slate_id text,
  status text not null default 'REVIEW_REQUIRED' check (status='REVIEW_REQUIRED'),
  reason text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function public.genome_mark_review_required(
  p_prediction_id text,
  p_slate_id text,
  p_reason text,
  p_payload jsonb
)
returns jsonb
language plpgsql
set search_path to ''
as $$
declare
  v_existing public.genome_postgame_reviews%rowtype;
begin
  if p_prediction_id is null or btrim(p_prediction_id)='' then
    raise exception 'prediction_id is required';
  end if;
  if p_reason is null or btrim(p_reason)='' then
    raise exception 'review reason is required';
  end if;
  if exists (select 1 from public.shin2_settlements where prediction_id=p_prediction_id) then
    raise exception 'settled prediction cannot be marked review required';
  end if;
  if not exists (select 1 from public.shin2_verdicts where prediction_id=p_prediction_id) then
    raise exception 'prediction does not exist';
  end if;

  perform pg_advisory_xact_lock(hashtextextended('genome-review:' || p_prediction_id,0));
  select * into v_existing from public.genome_postgame_reviews where prediction_id=p_prediction_id;
  if found then
    if v_existing.slate_id is distinct from p_slate_id
       or v_existing.reason is distinct from p_reason
       or v_existing.payload is distinct from coalesce(p_payload,'{}'::jsonb) then
      raise exception using errcode='23505', message='Prediction already has a conflicting review-required record';
    end if;
    return to_jsonb(v_existing);
  end if;

  insert into public.genome_postgame_reviews(prediction_id,slate_id,reason,payload)
  values(p_prediction_id,p_slate_id,p_reason,coalesce(p_payload,'{}'::jsonb))
  returning * into v_existing;
  return to_jsonb(v_existing);
end;
$$;

drop function if exists public.genome_review_queue(text);

create function public.genome_review_queue(p_slate_id text default null)
returns table(
  prediction_id text,
  slate_id text,
  sport text,
  prediction_type text,
  selection text,
  probability double precision,
  roar_action text,
  independent_group_key text,
  game_start_at timestamptz,
  freeze_fingerprint text,
  frozen_at timestamptz,
  game_id text,
  payload jsonb
)
language sql
stable
set search_path to ''
as $$
  select
    v.prediction_id,
    nullif(v.payload->>'slate_id',''),
    coalesce(
      nullif(v.payload->>'sport',''),
      case
        when v.payload->>'game_id' like 'MLB-%' then 'MLB'
        when v.payload->>'game_id' like 'NFL-%' then 'NFL'
        when v.payload->>'game_id' like 'CFB-%' or v.payload->>'game_id' like 'NCAAF-%' then 'CFB'
        else 'UNKNOWN'
      end
    ),
    v.payload->>'prediction_type',
    v.payload->>'selection',
    coalesce(nullif(v.payload->>'probability','')::double precision,
             nullif(v.payload->>'model_probability','')::double precision),
    case when v.payload->>'roar_action' in ('ROAR','NO_ROAR') then v.payload->>'roar_action' else 'LEGACY' end,
    coalesce(nullif(v.payload->>'independent_group_key',''),v.prediction_id),
    to_timestamp((v.payload->>'game_start_at')::double precision),
    v.freeze_fingerprint,
    to_timestamp(v.logged_at),
    v.payload->>'game_id',
    v.payload
  from public.shin2_verdicts v
  left join public.shin2_settlements s on s.prediction_id=v.prediction_id
  left join public.genome_postgame_reviews r on r.prediction_id=v.prediction_id
  where s.prediction_id is null
    and r.prediction_id is null
    and v.payload->>'record_kind'='PREDICTION'
    and (v.payload->>'game_start_at')::double precision <= extract(epoch from clock_timestamp())
    and (p_slate_id is null or v.payload->>'slate_id'=p_slate_id)
  order by (v.payload->>'game_start_at')::double precision, v.prediction_id;
$$;

create or replace function public.genome_postmortem_queue(p_slate_id text default null)
returns table(
  prediction_id text,
  slate_id text,
  verdict_payload jsonb,
  settlement_payload jsonb,
  freeze_fingerprint text
)
language sql
stable
set search_path to ''
as $$
  select v.prediction_id,
         nullif(v.payload->>'slate_id',''),
         v.payload,
         s.payload,
         v.freeze_fingerprint
  from public.shin2_verdicts v
  join public.shin2_settlements s on s.prediction_id=v.prediction_id
  left join public.prediction_postmortems p on p.prediction_id=v.prediction_id
  where p.prediction_id is null
    and v.payload->>'record_kind'='PREDICTION'
    and (p_slate_id is null or v.payload->>'slate_id'=p_slate_id)
  order by v.prediction_id;
$$;

create or replace function public.genome_molt_queue(p_slate_id text default null)
returns table(
  memory_id text,
  prediction_id text,
  slate_id text,
  verdict_payload jsonb,
  postmortem jsonb
)
language sql
stable
set search_path to ''
as $$
  select p.memory_id,
         p.prediction_id,
         nullif(v.payload->>'slate_id',''),
         v.payload,
         to_jsonb(p)
  from public.prediction_postmortems p
  join public.shin2_verdicts v on v.prediction_id=p.prediction_id
  where p.eligible_for_pattern_learning is true
    and not exists (
      select 1 from public.genome_experience_evidence e
      where e.postmortem_memory_id=p.memory_id
    )
    and (p_slate_id is null or v.payload->>'slate_id'=p_slate_id)
  order by p.created_at,p.prediction_id;
$$;

create or replace function public.genome_record_postmortem(
  p_memory_id text,
  p_prediction_id text,
  p_payload jsonb
)
returns jsonb
language plpgsql
set search_path to ''
as $$
declare
  v_existing public.prediction_postmortems%rowtype;
  v_verdict public.shin2_verdicts%rowtype;
  v_learning double precision;
  v_expectation text;
  v_reasoning text;
  v_info text;
  v_variance text;
begin
  if p_memory_id is null or btrim(p_memory_id)='' then raise exception 'memory_id is required'; end if;
  if p_prediction_id is null or btrim(p_prediction_id)='' then raise exception 'prediction_id is required'; end if;
  if not exists (select 1 from public.shin2_settlements where prediction_id=p_prediction_id) then
    raise exception 'canonical settlement is required before postmortem';
  end if;
  select * into strict v_verdict from public.shin2_verdicts where prediction_id=p_prediction_id;

  v_learning := nullif(p_payload->>'learning_value','')::double precision;
  if v_learning is not null and (v_learning < 0 or v_learning > 1) then raise exception 'invalid learning_value'; end if;
  v_expectation := coalesce(nullif(p_payload->>'expectation_quality',''),'UNKNOWN');
  v_reasoning := coalesce(nullif(p_payload->>'reasoning_quality',''),'UNKNOWN');
  v_info := coalesce(nullif(p_payload->>'outcome_informativeness',''),'UNKNOWN');
  v_variance := coalesce(nullif(p_payload->>'variance_class',''),'UNKNOWN');
  if v_expectation not in ('GOOD','MIXED','BAD','UNKNOWN') then raise exception 'invalid expectation_quality'; end if;
  if v_reasoning not in ('GOOD','MIXED','BAD','UNKNOWN') then raise exception 'invalid reasoning_quality'; end if;
  if v_info not in ('HIGH','MEDIUM','LOW','UNKNOWN') then raise exception 'invalid outcome_informativeness'; end if;
  if v_variance not in ('EXPECTED_VARIANCE','UNEXPECTED_EVENT','MODEL_MISS','DATA_ISSUE','CALIBRATION_ISSUE','UNKNOWN') then raise exception 'invalid variance_class'; end if;

  perform pg_advisory_xact_lock(hashtextextended('genome-postmortem:' || p_prediction_id,0));
  select * into v_existing from public.prediction_postmortems where prediction_id=p_prediction_id;
  if found then
    if v_existing.memory_id is distinct from p_memory_id
       or v_existing.expectation_quality is distinct from v_expectation
       or v_existing.reasoning_quality is distinct from v_reasoning
       or v_existing.variance_class is distinct from v_variance
       or v_existing.learning_value is distinct from v_learning
       or v_existing.correction_hypothesis is distinct from coalesce(p_payload->'correction_hypothesis','{}'::jsonb)
       or v_existing.evidence is distinct from coalesce(p_payload->'evidence','{}'::jsonb) then
      raise exception using errcode='23505', message='Prediction already has a conflicting postmortem';
    end if;
    return to_jsonb(v_existing);
  end if;

  insert into public.prediction_postmortems(
    memory_id,prediction_id,game_id,sport,expected_state,actual_state,deltas,primary_failure,
    secondary_factors,data_quality,confidence_assessment,calibration_assessment,segment,evidence,
    provenance,causal_confidence,correction_hypothesis,evolve_action,schema_version,
    expectation_quality,reasoning_quality,outcome_informativeness,variance_class,learning_value,
    eligible_for_pattern_learning,learning_notes
  ) values (
    p_memory_id,
    p_prediction_id,
    v_verdict.payload->>'game_id',
    coalesce(nullif(v_verdict.payload->>'sport',''),'UNKNOWN'),
    coalesce(p_payload->'expected_state','{}'::jsonb),
    coalesce(p_payload->'actual_state','{}'::jsonb),
    coalesce(p_payload->'deltas','{}'::jsonb),
    nullif(p_payload->>'primary_failure',''),
    coalesce(p_payload->'secondary_factors','[]'::jsonb),
    coalesce(p_payload->'data_quality','{}'::jsonb),
    coalesce(p_payload->'confidence_assessment','{}'::jsonb),
    coalesce(p_payload->'calibration_assessment','{}'::jsonb),
    coalesce(p_payload->'segment','{}'::jsonb),
    coalesce(p_payload->'evidence','{}'::jsonb),
    coalesce(p_payload->'provenance','[]'::jsonb),
    nullif(p_payload->>'causal_confidence','')::double precision,
    coalesce(p_payload->'correction_hypothesis','{}'::jsonb),
    coalesce(p_payload->'evolve_action','{}'::jsonb),
    '0.3',
    v_expectation,
    v_reasoning,
    v_info,
    v_variance,
    v_learning,
    coalesce((p_payload->>'eligible_for_pattern_learning')::boolean,false),
    coalesce(p_payload->'learning_notes','{}'::jsonb)
  ) returning * into v_existing;

  return to_jsonb(v_existing);
end;
$$;

alter table public.genome_experience_hypotheses
  drop constraint if exists genome_experience_hypotheses_lifecycle_status_check;

alter table public.genome_experience_hypotheses
  add constraint genome_experience_hypotheses_lifecycle_status_check
  check (lifecycle_status in ('OBSERVED','CANDIDATE','SUPPORTED','VALIDATED','MATURE','ACTIVE','CONTESTED','DECAYING','RETIRED'));

create or replace function public.genome_register_experience_hypothesis(p_payload jsonb)
returns jsonb
language plpgsql
set search_path to ''
as $$
declare
  v_existing public.genome_experience_hypotheses%rowtype;
  v_id text := nullif(p_payload->>'hypothesis_id','');
  v_sport text := nullif(p_payload->>'sport','');
  v_prediction_type text := nullif(p_payload->>'prediction_type','');
  v_segment_key text := coalesce(nullif(p_payload->>'segment_key',''),'default');
  v_hypothesis text := nullif(p_payload->>'hypothesis','');
  v_scope jsonb := coalesce(p_payload->'scope','{}'::jsonb);
begin
  if v_id is null or v_sport is null or v_prediction_type is null or v_hypothesis is null then
    raise exception 'hypothesis_id, sport, prediction_type, and hypothesis are required';
  end if;

  perform pg_advisory_xact_lock(hashtextextended('genome-hypothesis:' || v_id,0));
  select * into v_existing from public.genome_experience_hypotheses where hypothesis_id=v_id;
  if found then
    if v_existing.sport is distinct from v_sport
       or v_existing.prediction_type is distinct from v_prediction_type
       or v_existing.segment_key is distinct from v_segment_key
       or v_existing.hypothesis is distinct from v_hypothesis
       or v_existing.scope is distinct from v_scope then
      raise exception using errcode='23505', message='Hypothesis id already exists with conflicting canonical fields';
    end if;
    return to_jsonb(v_existing);
  end if;

  insert into public.genome_experience_hypotheses(
    hypothesis_id,sport,prediction_type,segment_key,hypothesis,scope,
    lifecycle_status,deployment_status,predictive_evidence_status,causal_claim_status,human_approval_required
  ) values (
    v_id,v_sport,v_prediction_type,v_segment_key,v_hypothesis,v_scope,
    'OBSERVED','SHADOW','UNPROVEN','UNPROVEN',true
  ) returning * into v_existing;

  return to_jsonb(v_existing);
end;
$$;

commit;
