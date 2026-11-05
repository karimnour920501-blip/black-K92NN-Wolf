CREATE TABLE IF NOT EXISTS projects (
 id uuid PRIMARY KEY,
 name varchar(120) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS servers (
 id uuid PRIMARY KEY,
 project_id uuid NOT NULL REFERENCES projects(id),
 label varchar(120) NOT NULL,
 hostname varchar(253) NOT NULL,
 ssh_port integer NOT NULL CHECK (ssh_port BETWEEN 1 AND 65535),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 action text NOT NULL,
 target text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
