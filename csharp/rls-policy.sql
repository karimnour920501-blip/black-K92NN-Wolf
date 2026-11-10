-- RLS policy pilot. Run as database owner in ephemeral CI.
-- API switches into the restricted role transactionally; owner connection remains a production risk.
-- A future deployment must use a separate non-owner login with no BYPASSRLS.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='blackwolf_tenant_runtime') THEN
    CREATE ROLE blackwolf_tenant_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;
GRANT blackwolf_tenant_runtime TO blackwolf;
GRANT USAGE ON SCHEMA public TO blackwolf_tenant_runtime;
GRANT SELECT, INSERT ON tenant_projects TO blackwolf_tenant_runtime;
ALTER TABLE tenant_projects ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_projects_isolation ON tenant_projects;
CREATE POLICY tenant_projects_isolation ON tenant_projects
  FOR ALL TO blackwolf_tenant_runtime
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true),'')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true),'')::uuid);
-- Do not use caller-controlled tenant_id directly in a public database connection.
-- The trusted API must authenticate the caller and SET LOCAL app.tenant_id in a transaction.
