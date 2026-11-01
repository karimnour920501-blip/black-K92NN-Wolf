-- Run after migrations and grants as database admin; test statements execute as wolf_app.
BEGIN;
SET LOCAL ROLE wolf_app;
DO $$ BEGIN
 IF (SELECT count(*) FROM workspace_projects) <> 0 THEN
  RAISE EXCEPTION 'RLS_FAIL: rows visible without tenant context';
 END IF;
END $$;
SELECT set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
INSERT INTO workspace_projects(id,tenant_id,name) VALUES
('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','11111111-1111-4111-8111-111111111111','tenant-a');
SELECT set_config('app.tenant_id', '22222222-2222-4222-8222-222222222222', true);
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM workspace_projects WHERE id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa') THEN
  RAISE EXCEPTION 'RLS_FAIL: cross-tenant row visible';
 END IF;
END $$;
DO $$
DECLARE rejected boolean := false;
BEGIN
 BEGIN
  INSERT INTO workspace_projects(id,tenant_id,name) VALUES
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','11111111-1111-4111-8111-111111111111','cross-tenant');
 EXCEPTION WHEN check_violation OR insufficient_privilege THEN
  rejected := true;
 END;
 IF NOT rejected THEN
  RAISE EXCEPTION 'RLS_FAIL: cross-tenant insert was accepted';
 END IF;
END $$;
ROLLBACK;
