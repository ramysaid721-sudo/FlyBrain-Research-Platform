-- Capability-token authorization for asynchronous task and task-group status.
-- A 256-bit random token is issued by MCP; only its SHA-256 hex digest is persisted.
-- Existing rows remain intact with NULL hashes. UUID-only status access is retired.

ALTER TABLE public.flybrain_task_runs ADD COLUMN access_token_hash text;
ALTER TABLE public.flybrain_task_runs
  ADD CONSTRAINT flybrain_task_runs_access_token_hash_format
  CHECK (access_token_hash IS NULL OR access_token_hash ~ '^[0-9a-f]{64}$') NOT VALID;
ALTER TABLE public.flybrain_task_runs VALIDATE CONSTRAINT flybrain_task_runs_access_token_hash_format;

ALTER TABLE private.flybrain_task_groups ADD COLUMN access_token_hash text;
ALTER TABLE private.flybrain_task_groups
  ADD CONSTRAINT flybrain_task_groups_access_token_hash_format
  CHECK (access_token_hash IS NULL OR access_token_hash ~ '^[0-9a-f]{64}$') NOT VALID;
ALTER TABLE private.flybrain_task_groups VALIDATE CONSTRAINT flybrain_task_groups_access_token_hash_format;

CREATE OR REPLACE FUNCTION public.flybrain_enqueue_task(
  p_task_type text, p_payload jsonb, p_idempotency_key text, p_access_token_hash text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'pgmq'
AS $function$
DECLARE
  v_task_id uuid;
  v_message_id bigint;
  v_existing public.flybrain_task_runs%ROWTYPE;
BEGIN
  IF p_task_type <> 'research_search' THEN RAISE EXCEPTION 'unsupported_task_type'; END IF;
  IF p_access_token_hash IS NULL OR p_access_token_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'invalid_access_token_hash';
  END IF;
  IF jsonb_typeof(p_payload) <> 'object'
     OR (SELECT count(*) FROM jsonb_object_keys(p_payload)) <> 2
     OR NOT (p_payload ? 'query') OR NOT (p_payload ? 'page_size')
     OR jsonb_typeof(p_payload->'query') <> 'string'
     OR length(btrim(p_payload->>'query')) < 1 OR length(p_payload->>'query') > 400
     OR jsonb_typeof(p_payload->'page_size') <> 'number'
     OR (p_payload->>'page_size')::int NOT BETWEEN 1 AND 10 THEN
    RAISE EXCEPTION 'invalid_task_payload';
  END IF;
  IF p_idempotency_key IS NOT NULL THEN
    IF length(p_idempotency_key) < 8 OR length(p_idempotency_key) > 120 THEN
      RAISE EXCEPTION 'invalid_idempotency_key';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(p_idempotency_key,0));
    SELECT * INTO v_existing FROM public.flybrain_task_runs WHERE idempotency_key=p_idempotency_key;
    IF FOUND THEN
      IF v_existing.task_type <> p_task_type OR v_existing.payload <> p_payload THEN
        RAISE EXCEPTION 'idempotency_key_conflict';
      END IF;
      RETURN jsonb_build_object('task_id',v_existing.task_id,'status',v_existing.status,'duplicate',true);
    END IF;
  END IF;
  v_task_id := gen_random_uuid();
  SELECT * INTO v_message_id FROM pgmq.send('flybrain_tasks',jsonb_build_object('task_id',v_task_id,'task_type',p_task_type));
  INSERT INTO public.flybrain_task_runs(task_id,queue_message_id,task_type,payload,idempotency_key,access_token_hash)
  VALUES(v_task_id,v_message_id,p_task_type,p_payload,p_idempotency_key,p_access_token_hash);
  RETURN jsonb_build_object('task_id',v_task_id,'status','queued','duplicate',false);
END
$function$;

CREATE OR REPLACE FUNCTION public.flybrain_enqueue_task_group(
  p_tasks jsonb, p_idempotency_key text, p_data_classification text, p_access_token_hash text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'private'
AS $function$
DECLARE
  v_group_id uuid;
  v_existing private.flybrain_task_groups%ROWTYPE;
  v_item jsonb;
  v_result jsonb;
  v_task_id uuid;
  v_count integer;
  v_ordinal integer := 0;
BEGIN
  IF p_data_classification IS DISTINCT FROM 'public' THEN RAISE EXCEPTION 'task_group_public_data_only'; END IF;
  IF p_access_token_hash IS NULL OR p_access_token_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'invalid_access_token_hash';
  END IF;
  IF p_idempotency_key IS NULL OR length(p_idempotency_key) < 8 OR length(p_idempotency_key) > 100 THEN
    RAISE EXCEPTION 'invalid_group_idempotency_key';
  END IF;
  IF jsonb_typeof(p_tasks) <> 'array' THEN RAISE EXCEPTION 'invalid_task_group'; END IF;
  v_count := jsonb_array_length(p_tasks);
  IF v_count < 1 OR v_count > 10 THEN RAISE EXCEPTION 'invalid_task_group_size'; END IF;

  PERFORM pg_advisory_xact_lock(hashtextextended('group:' || p_idempotency_key,0));
  SELECT * INTO v_existing FROM private.flybrain_task_groups WHERE idempotency_key=p_idempotency_key;
  IF FOUND THEN
    IF v_existing.tasks_signature <> p_tasks THEN RAISE EXCEPTION 'group_idempotency_key_conflict'; END IF;
    RETURN jsonb_build_object('group_id',v_existing.group_id,'expected_tasks',v_existing.expected_tasks,'duplicate',true);
  END IF;

  INSERT INTO private.flybrain_task_groups(idempotency_key,expected_tasks,tasks_signature,access_token_hash)
  VALUES(p_idempotency_key,v_count,p_tasks,p_access_token_hash) RETURNING group_id INTO v_group_id;

  FOR v_item IN SELECT value FROM jsonb_array_elements(p_tasks) LOOP
    v_ordinal := v_ordinal + 1;
    IF jsonb_typeof(v_item) <> 'object'
       OR (SELECT count(*) FROM jsonb_object_keys(v_item)) <> 2
       OR NOT (v_item ? 'query') OR NOT (v_item ? 'page_size')
       OR jsonb_typeof(v_item->'query') <> 'string'
       OR length(btrim(v_item->>'query')) < 1 OR length(v_item->>'query') > 400
       OR jsonb_typeof(v_item->'page_size') <> 'number'
       OR (v_item->>'page_size')::int NOT BETWEEN 1 AND 10 THEN
      RAISE EXCEPTION 'invalid_task_group_item';
    END IF;
    v_result := public.flybrain_enqueue_task(
      'research_search',v_item,left('grp:' || p_idempotency_key || ':' || v_ordinal::text,120),p_access_token_hash
    );
    v_task_id := (v_result->>'task_id')::uuid;
    INSERT INTO private.flybrain_task_group_items(group_id,task_id,ordinal)
    VALUES(v_group_id,v_task_id,v_ordinal);
  END LOOP;
  RETURN jsonb_build_object('group_id',v_group_id,'expected_tasks',v_count,'duplicate',false);
END
$function$;

CREATE OR REPLACE FUNCTION public.flybrain_task_status(p_task_id uuid,p_access_token_hash text)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'private'
AS $function$
  SELECT jsonb_build_object(
    'task_id',t.task_id,'task_type',t.task_type,'status',t.status,'attempts',t.attempts,
    'error_code',t.error_code,'created_at',t.created_at,'updated_at',t.updated_at,
    'completed_at',t.completed_at,'result',t.result,
    'events',coalesce((
      SELECT jsonb_agg(jsonb_build_object(
        'event_type',e.event_type,'attempt',e.attempt,'occurred_at',e.occurred_at,'metadata',e.metadata
      ) ORDER BY e.occurred_at DESC)
      FROM (
        SELECT event_type,attempt,occurred_at,metadata
        FROM private.flybrain_task_events WHERE task_id=t.task_id
        ORDER BY occurred_at DESC LIMIT 20
      ) e
    ),'[]'::jsonb)
  )
  FROM public.flybrain_task_runs t
  WHERE t.task_id=p_task_id
    AND p_access_token_hash ~ '^[0-9a-f]{64}$'
    AND t.access_token_hash=p_access_token_hash
$function$;

CREATE OR REPLACE FUNCTION public.flybrain_task_group_status(p_group_id uuid,p_access_token_hash text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'private'
AS $function$
DECLARE
  v_group private.flybrain_task_groups%ROWTYPE;
  v_completed integer;
  v_failed integer;
  v_active integer;
  v_items jsonb;
  v_summary_items jsonb;
  v_status text;
  v_result jsonb;
  v_results_omitted boolean := false;
BEGIN
  SELECT * INTO v_group FROM private.flybrain_task_groups WHERE group_id=p_group_id;
  IF NOT FOUND OR p_access_token_hash IS NULL OR p_access_token_hash !~ '^[0-9a-f]{64}$'
     OR v_group.access_token_hash IS DISTINCT FROM p_access_token_hash THEN RETURN NULL; END IF;

  SELECT count(*) FILTER (WHERE t.status='completed'),
         count(*) FILTER (WHERE t.status='failed'),
         count(*) FILTER (WHERE t.status IN ('queued','running')),
         jsonb_agg(jsonb_build_object('task_id',t.task_id,'ordinal',i.ordinal,'status',t.status,
           'attempts',t.attempts,'error_code',t.error_code,'result',t.result) ORDER BY i.ordinal),
         jsonb_agg(jsonb_build_object('task_id',t.task_id,'ordinal',i.ordinal,'status',t.status,
           'attempts',t.attempts,'error_code',t.error_code) ORDER BY i.ordinal)
  INTO v_completed,v_failed,v_active,v_items,v_summary_items
  FROM private.flybrain_task_group_items i
  JOIN public.flybrain_task_runs t ON t.task_id=i.task_id
  WHERE i.group_id=p_group_id;

  IF v_active > 0 AND v_failed > 0 THEN v_status := 'running_with_errors';
  ELSIF v_active > 0 THEN v_status := 'running';
  ELSIF v_failed > 0 THEN v_status := 'completed_with_errors';
  ELSE v_status := 'completed'; END IF;

  IF octet_length(coalesce(v_items,'[]'::jsonb)::text) > 48000 THEN
    v_items := v_summary_items; v_results_omitted := true;
  END IF;
  v_result := jsonb_build_object('group_id',v_group.group_id,'expected_tasks',v_group.expected_tasks,
    'completed_tasks',v_completed,'failed_tasks',v_failed,'active_tasks',v_active,'status',v_status,
    'results_omitted',v_results_omitted,'items',coalesce(v_items,'[]'::jsonb));
  RETURN v_result;
END
$function$;

-- Remove all UUID-only RPC signatures.
DROP FUNCTION public.flybrain_task_group_status(uuid);
DROP FUNCTION public.flybrain_task_status(uuid);
DROP FUNCTION public.flybrain_enqueue_task_group(jsonb,text,text);
DROP FUNCTION public.flybrain_enqueue_task(text,jsonb,text);

REVOKE ALL ON FUNCTION public.flybrain_enqueue_task(text,jsonb,text,text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.flybrain_enqueue_task_group(jsonb,text,text,text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.flybrain_task_status(uuid,text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.flybrain_task_group_status(uuid,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.flybrain_enqueue_task(text,jsonb,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.flybrain_enqueue_task_group(jsonb,text,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.flybrain_task_status(uuid,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.flybrain_task_group_status(uuid,text) TO service_role;

NOTIFY pgrst, 'reload schema';
