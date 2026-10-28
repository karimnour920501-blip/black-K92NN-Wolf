"""Versioned, transactional migration runner; must connect as pay_migrator."""
import hashlib
from pathlib import Path
from sqlalchemy import text
from app.persistence.database import engine, Base
from app.persistence import models  # noqa: F401

with engine.begin() as conn:
    who = conn.execute(text('SELECT current_user')).scalar_one()
    if who != 'pay_migrator':
        raise RuntimeError('Migration requires pay_migrator role')
    conn.execute(text('SELECT pg_advisory_xact_lock(920501001)'))
    conn.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())'))
    existing = {r.version: r.sha256 for r in conn.execute(text('SELECT version, sha256 FROM schema_migrations'))}
    if not existing:
        Base.metadata.create_all(bind=conn)
    for path in sorted(Path(__file__).resolve().parents[1].joinpath('migrations').glob('[0-9]*.sql')):
        sql = path.read_text()
        digest = hashlib.sha256(sql.encode()).hexdigest()
        if path.name in existing:
            if existing[path.name] != digest:
                raise RuntimeError(f'Migration checksum mismatch: {path.name}')
            continue
        conn.exec_driver_sql(sql)
        conn.execute(text('INSERT INTO schema_migrations(version, sha256) VALUES (:v,:h)'), {'v':path.name,'h':digest})
    # Explicit grants cover preexisting tables, not just future objects.
    conn.execute(text('GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO pay_runtime'))
    conn.execute(text('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pay_runtime'))
    conn.execute(text('REVOKE DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM pay_runtime'))
print('PASS: migrations applied with dedicated owner role')
