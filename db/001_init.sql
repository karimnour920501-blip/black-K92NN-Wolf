CREATE TABLE IF NOT EXISTS command_evidence (
 sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL,
 actor_id text NOT NULL,
 command_name text NOT NULL,
 request_hash char(64) NOT NULL,
 result_hash char(64) NOT NULL,
 previous_hash char(64) NOT NULL,
 entry_hash char(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS command_evidence_tenant_sequence ON command_evidence(tenant_id, sequence DESC);
ALTER TABLE command_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE command_evidence FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS command_evidence_tenant ON command_evidence;
CREATE POLICY command_evidence_tenant ON command_evidence USING (
 tenant_id = NULLIF(current_setting('app.tenant_id', true),'')::uuid
) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true),'')::uuid);
