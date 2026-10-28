# UER v0.1.1 Reliability Patch

This is a source patch, **not a verified production release**.

## Included
- SQLite-driven pending job recovery (Channel no longer authoritative).
- Interrupted `running` jobs returned to `queued` on startup.
- Manifest source copy limits: 500 files, 20 MB total, 5 MB each.
- Bounded retained Docker output (stdout/stderr drained).
- Pinned Docker image references required via `UER_PYTHON_IMAGE` and `UER_NODE_IMAGE` (`repository@sha256:<digest>`).
- Loopback-only HTTP requests; also bind Kestrel to 127.0.0.1.
- Smoke test awaits replay completion and compares artifact hashes.

## Required before production
- Implement atomic job claiming and transactional status + ledger recording; use only one API instance.
- Resolve startup interruption of abandoned Docker containers, harden timeouts, and add disk quotas at host/container level.
- Add signed external ledger anchoring; SQLite chain alone is tamper-evident only against limited adversaries.
- Audit symlink/path traversal and file races during source copying.
- Authenticated API, tenant isolation, secure remote execution; currently LOCAL TRUSTED USE ONLY.
- Real .NET compilation, Docker integration, fault injection, and acceptance tests.

## Run
Set image digests from your trusted registry (never use mutable tags), then:

```bash
export UER_PYTHON_IMAGE='python@sha256:REPLACE_WITH_REAL_64_HEX_DIGEST'
export UER_NODE_IMAGE='node@sha256:REPLACE_WITH_REAL_64_HEX_DIGEST'
UER_ROOT="$PWD/data" UER_PROJECTS="$PWD/projects" dotnet run --project src/Uer.Api --urls http://127.0.0.1:5080
bash scripts/smoke.sh
```

Image digests are placeholders until verified and supplied by the operator. Docker images must already be pulled.
