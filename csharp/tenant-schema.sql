CREATE TABLE IF NOT EXISTS tenants (
 id uuid PRIMARY KEY,
 name varchar(120) NOT NULL,
 api_key_hash char(64) NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS tenant_projects (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id),
 name varchar(120) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tenant_projects_tenant_idx ON tenant_projects(tenant_id, created_at DESC);
-- CI-only bootstrap via privileged local Admin Token. Production requires external identity and RLS.
