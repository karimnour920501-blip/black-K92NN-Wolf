DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wolf_app') THEN
   CREATE ROLE wolf_app LOGIN;
 END IF;
END $$;
GRANT USAGE ON SCHEMA public TO wolf_app;
GRANT SELECT, INSERT ON command_evidence TO wolf_app;
GRANT USAGE, SELECT ON SEQUENCE command_evidence_sequence_seq TO wolf_app;
GRANT SELECT, INSERT ON workspace_projects TO wolf_app;
-- Set login password separately through secret management. Never commit credentials.
