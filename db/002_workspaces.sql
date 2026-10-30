CREATE TABLE IF NOT EXISTS workspace_projects (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 name varchar(120) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS workspace_projects_tenant_created ON workspace_projects(tenant_id, created_at DESC);
ALTER TABLE workspace_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_projects FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS workspace_projects_tenant ON workspace_projects;
CREATE POLICY workspace_projects_tenant ON workspace_projects
 USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
 WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
