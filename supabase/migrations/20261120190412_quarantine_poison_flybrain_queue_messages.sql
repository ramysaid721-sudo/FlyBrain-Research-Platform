-- Quarantine malformed and orphan queue messages so one bad payload cannot
-- repeatedly abort the worker claim transaction and block later messages.

CREATE OR REPLACE FUNCTION public.flybrain_claim_task(p_visibility_timeout integer DEFAULT 60)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'pgmq'
AS $function$
DECLARE
  v_msg record;
  v_task public.flybrain_task_runs%ROWTYPE;
  v_task_id uuid;
  v_task_id_text text;
  v_claim_token uuid := gen_random_uuid();
  v_remaining_seconds integer;
BEGIN
  IF p_visibility_timeout NOT BETWEEN 10 AND 300 THEN
    RAISE EXCEPTION 'invalid_visibility_timeout';
  END IF;

  SELECT * INTO v_msg
  FROM pgmq.read('flybrain_tasks', p_visibility_timeout, 1);

  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  IF jsonb_typeof(v_msg.message) IS DISTINCT FROM 'object'
     OR jsonb_typeof(v_msg.message->'task_id') IS DISTINCT FROM 'string' THEN
    PERFORM pgmq.archive('flybrain_tasks', v_msg.msg_id);
    RETURN NULL;
  END IF;

  v_task_id_text := v_msg.message->>'task_id';
  IF v_task_id_text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
    PERFORM pgmq.archive('flybrain_tasks', v_msg.msg_id);
    RETURN NULL;
  END IF;

  v_task_id := v_task_id_text::uuid;

  SELECT * INTO v_task
  FROM public.flybrain_task_runs
  WHERE task_id = v_task_id
  FOR UPDATE;

  IF NOT FOUND THEN
    PERFORM pgmq.archive('flybrain_tasks', v_msg.msg_id);
    RETURN NULL;
  END IF;

  IF v_task.status IN ('completed', 'failed') THEN
    PERFORM pgmq.archive('flybrain_tasks', v_msg.msg_id);
    RETURN NULL;
  END IF;

  IF v_task.attempts >= 3
     AND (v_task.status = 'queued'
          OR (v_task.status = 'running'
              AND (v_task.lease_expires_at IS NULL OR v_task.lease_expires_at <= now()))) THEN
    UPDATE public.flybrain_task_runs
    SET status = 'failed',
        error_code = 'worker_lease_expired_max_attempts',
        updated_at = now(),
        completed_at = now(),
        claim_token = NULL,
        lease_expires_at = NULL
    WHERE task_id = v_task_id;

    PERFORM pgmq.archive('flybrain_tasks', v_msg.msg_id);
    RETURN NULL;
  END IF;

  IF v_task.status = 'running'
     AND v_task.lease_expires_at IS NOT NULL
     AND v_task.lease_expires_at > now() THEN
    v_remaining_seconds := GREATEST(
      1,
      LEAST(300, ceil(extract(epoch FROM (v_task.lease_expires_at - now())))::integer)
    );
    PERFORM pgmq.set_vt('flybrain_tasks', v_msg.msg_id, v_remaining_seconds);
    RETURN NULL;
  END IF;

  IF v_task.status = 'queued'
     OR (v_task.status = 'running'
         AND (v_task.lease_expires_at IS NULL OR v_task.lease_expires_at <= now())) THEN
    UPDATE public.flybrain_task_runs
    SET status = 'running',
        attempts = attempts + 1,
        updated_at = now(),
        claim_token = v_claim_token,
        lease_expires_at = now() + make_interval(secs => p_visibility_timeout)
    WHERE task_id = v_task_id
      AND attempts < 3
    RETURNING * INTO v_task;

    IF FOUND THEN
      RETURN jsonb_build_object(
        'task_id', v_task.task_id,
        'message_id', v_msg.msg_id,
        'task_type', v_task.task_type,
        'payload', v_task.payload,
        'attempts', v_task.attempts,
        'claim_token', v_task.claim_token,
        'lease_expires_at', v_task.lease_expires_at
      );
    END IF;
  END IF;

  PERFORM pgmq.archive('flybrain_tasks', v_msg.msg_id);
  RETURN NULL;
END
$function$;

REVOKE ALL ON FUNCTION public.flybrain_claim_task(integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.flybrain_claim_task(integer) TO service_role;
