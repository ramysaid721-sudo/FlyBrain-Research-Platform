-- Run after the capability-token migration. All inserts and pgmq messages are rolled back.
BEGIN;
DO $capability_tests$
DECLARE
  v_hash text := repeat('a',64);
  v_wrong text := repeat('b',64);
  v_task jsonb;
  v_task_duplicate jsonb;
  v_group jsonb;
  v_group_duplicate jsonb;
  v_task_id uuid;
  v_group_id uuid;
BEGIN
  v_task := public.flybrain_enqueue_task('research_search',
    jsonb_build_object('query','capability token task rollback test','page_size',1),
    'capability-task-test-20261120',v_hash);
  IF (v_task->>'duplicate')::boolean THEN RAISE EXCEPTION 'new task unexpectedly marked duplicate'; END IF;
  v_task_id := (v_task->>'task_id')::uuid;
  IF public.flybrain_task_status(v_task_id,v_wrong) IS NOT NULL THEN RAISE EXCEPTION 'wrong task token accepted'; END IF;
  IF public.flybrain_task_status(v_task_id,v_hash) IS NULL THEN RAISE EXCEPTION 'correct task token rejected'; END IF;
  v_task_duplicate := public.flybrain_enqueue_task('research_search',
    jsonb_build_object('query','capability token task rollback test','page_size',1),
    'capability-task-test-20261120',v_wrong);
  IF NOT (v_task_duplicate->>'duplicate')::boolean THEN RAISE EXCEPTION 'task idempotency failed'; END IF;
  IF public.flybrain_task_status(v_task_id,v_hash) IS NULL OR
     public.flybrain_task_status(v_task_id,v_wrong) IS NOT NULL THEN
    RAISE EXCEPTION 'duplicate submission changed task capability';
  END IF;

  v_group := public.flybrain_enqueue_task_group(
    jsonb_build_array(jsonb_build_object('query','capability token group rollback test','page_size',1)),
    'capability-group-test-20261120','public',v_hash);
  IF (v_group->>'duplicate')::boolean THEN RAISE EXCEPTION 'new group unexpectedly marked duplicate'; END IF;
  v_group_id := (v_group->>'group_id')::uuid;
  IF public.flybrain_task_group_status(v_group_id,v_wrong) IS NOT NULL THEN RAISE EXCEPTION 'wrong group token accepted'; END IF;
  IF public.flybrain_task_group_status(v_group_id,v_hash) IS NULL THEN RAISE EXCEPTION 'correct group token rejected'; END IF;
  v_group_duplicate := public.flybrain_enqueue_task_group(
    jsonb_build_array(jsonb_build_object('query','capability token group rollback test','page_size',1)),
    'capability-group-test-20261120','public',v_wrong);
  IF NOT (v_group_duplicate->>'duplicate')::boolean THEN RAISE EXCEPTION 'group idempotency failed'; END IF;
  IF public.flybrain_task_group_status(v_group_id,v_hash) IS NULL OR
     public.flybrain_task_group_status(v_group_id,v_wrong) IS NOT NULL THEN
    RAISE EXCEPTION 'duplicate submission changed group capability';
  END IF;
END
$capability_tests$;
ROLLBACK;
