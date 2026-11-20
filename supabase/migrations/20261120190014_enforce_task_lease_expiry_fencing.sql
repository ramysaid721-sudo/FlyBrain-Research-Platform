-- Enforce strict lease-expiry fencing for task state transitions.
-- A worker whose lease has expired must not complete, fail, or defer a task,
-- even if its claim token has not yet been replaced by a subsequent worker.

CREATE OR REPLACE FUNCTION public.flybrain_complete_task(
  p_task_id uuid,
  p_message_id bigint,
  p_claim_token uuid,
  p_result jsonb
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'pgmq'
AS $function$
DECLARE
  v_count integer;
BEGIN
  IF jsonb_typeof(p_result) <> 'object' OR pg_column_size(p_result) > 65536 THEN
    RAISE EXCEPTION 'invalid_task_result';
  END IF;

  UPDATE public.flybrain_task_runs
  SET status='completed',
      result=p_result,
      error_code=NULL,
      updated_at=now(),
      completed_at=now(),
      claim_token=NULL,
      lease_expires_at=NULL
  WHERE task_id=p_task_id
    AND queue_message_id=p_message_id
    AND claim_token=p_claim_token
    AND status='running'
    AND lease_expires_at > now();

  GET DIAGNOSTICS v_count = ROW_COUNT;
  IF v_count=1 THEN
    PERFORM pgmq.archive('flybrain_tasks',p_message_id);
  END IF;
  RETURN v_count=1;
END
$function$;

CREATE OR REPLACE FUNCTION public.flybrain_fail_task(
  p_task_id uuid,
  p_message_id bigint,
  p_claim_token uuid,
  p_error_code text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'pgmq'
AS $function$
DECLARE
  v_task public.flybrain_task_runs%ROWTYPE;
BEGIN
  UPDATE public.flybrain_task_runs
  SET status=CASE WHEN attempts>=3 THEN 'failed' ELSE 'queued' END,
      error_code=left(coalesce(p_error_code,'task_failed'),80),
      updated_at=now(),
      completed_at=CASE WHEN attempts>=3 THEN now() ELSE NULL END,
      claim_token=NULL,
      lease_expires_at=NULL
  WHERE task_id=p_task_id
    AND queue_message_id=p_message_id
    AND claim_token=p_claim_token
    AND status='running'
    AND lease_expires_at > now()
  RETURNING * INTO v_task;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('updated',false,'reason','stale_or_expired_claim');
  END IF;

  IF v_task.status='failed' THEN
    PERFORM pgmq.archive('flybrain_tasks',p_message_id);
    RETURN jsonb_build_object('updated',true,'status','failed');
  END IF;

  RETURN jsonb_build_object('updated',true,'status','queued','retry_after_visibility_timeout',true);
END
$function$;

CREATE OR REPLACE FUNCTION public.flybrain_defer_task(
  p_task_id uuid,
  p_message_id bigint,
  p_claim_token uuid,
  p_error_code text,
  p_retry_delay integer
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'pgmq'
AS $function$
DECLARE
  v_task public.flybrain_task_runs%ROWTYPE;
BEGIN
  IF p_retry_delay IS NULL OR p_retry_delay NOT BETWEEN 60 AND 900 THEN
    RAISE EXCEPTION 'invalid_retry_delay';
  END IF;

  UPDATE public.flybrain_task_runs
  SET status = CASE WHEN attempts >= 3 THEN 'failed' ELSE 'queued' END,
      error_code = left(coalesce(p_error_code, 'crossref_http_429'), 80),
      updated_at = now(),
      completed_at = CASE WHEN attempts >= 3 THEN now() ELSE NULL END,
      claim_token = NULL,
      lease_expires_at = NULL
  WHERE task_id = p_task_id
    AND queue_message_id = p_message_id
    AND claim_token = p_claim_token
    AND status = 'running'
    AND lease_expires_at > now()
  RETURNING * INTO v_task;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('updated', false, 'reason', 'stale_or_expired_claim');
  END IF;

  IF v_task.status = 'failed' THEN
    PERFORM pgmq.archive('flybrain_tasks', p_message_id);
    RETURN jsonb_build_object('updated', true, 'status', 'failed', 'reason', 'max_attempts');
  END IF;

  PERFORM pgmq.set_vt('flybrain_tasks', p_message_id, p_retry_delay);
  RETURN jsonb_build_object(
    'updated', true,
    'status', 'queued',
    'retry_delay_seconds', p_retry_delay
  );
END
$function$;

REVOKE ALL ON FUNCTION public.flybrain_complete_task(uuid,bigint,uuid,jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.flybrain_fail_task(uuid,bigint,uuid,text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.flybrain_defer_task(uuid,bigint,uuid,text,integer) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.flybrain_complete_task(uuid,bigint,uuid,jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.flybrain_fail_task(uuid,bigint,uuid,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.flybrain_defer_task(uuid,bigint,uuid,text,integer) TO service_role;
