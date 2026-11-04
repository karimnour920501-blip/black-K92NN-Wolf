BEGIN;
INSERT INTO tenants(id,name,api_key_hash) VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','rls-a',repeat('a',64)),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','rls-b',repeat('b',64));
INSERT INTO tenant_projects(id,tenant_id,name) VALUES
 ('11111111-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','private-a'),
 ('22222222-2222-4222-8222-222222222222','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','private-b');
SET LOCAL ROLE blackwolf_tenant_runtime;
DO $$
BEGIN
 IF (SELECT count(*) FROM tenant_projects) <> 0 THEN RAISE EXCEPTION 'RLS without context leaked rows'; END IF;
END $$;
SELECT set_config('app.tenant_id','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM tenant_projects) <> 1 THEN RAISE EXCEPTION 'RLS tenant A did not see exactly one row'; END IF;
 IF EXISTS(SELECT 1 FROM tenant_projects WHERE name='private-b') THEN RAISE EXCEPTION 'RLS cross-tenant read'; END IF;
END $$;
SELECT set_config('app.tenant_id','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM tenant_projects) <> 1 THEN RAISE EXCEPTION 'RLS tenant B did not see exactly one row'; END IF;
 IF EXISTS(SELECT 1 FROM tenant_projects WHERE name='private-a') THEN RAISE EXCEPTION 'RLS cross-tenant read'; END IF;
END $$;
ROLLBACK;
