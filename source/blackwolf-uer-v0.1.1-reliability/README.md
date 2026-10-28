# BLACK-K92N-WOLF — UER v0.1 (local MVP)

**Status:** source implementation, **NOT production certified**. Docker/.NET execution has not been verified in the generation environment.

## Requirements
- .NET SDK 8, Docker Engine (daemon running), Python 3 for smoke script.
- Trusted local project directories only. Do not expose this API to the Internet.

## Start
```bash
docker pull python:3.12-slim
docker pull node:22-bookworm-slim
dotnet restore src/Uer.Api/Uer.Api.csproj
UER_PROJECTS="$PWD/projects" UER_ROOT="$PWD/data" dotnet run --project src/Uer.Api --urls http://127.0.0.1:5080
```
In a second terminal:
```bash
bash scripts/smoke.sh
curl http://127.0.0.1:5080/ledger/verify
```

## Endpoints
- `GET /health`, `GET /projects`, `POST /jobs` with `{"project":"proxylogon-dfir"}`
- `GET /jobs/{id}`, `POST /jobs/{id}/replay`, `GET /ledger`, `GET /ledger/verify`.

## Security boundaries
No arbitrary commands from manifest. The `test` operation is hardcoded per adapter. Docker invocation uses ArgumentList, no shell. Containers run without network, capabilities, root, writable rootfs, or privilege escalation, and with resource/time bounds. **Docker socket/daemon is privileged**; run only on a trusted developer machine, not a shared public host. Bind-mounted output permissions may require host setup; no untrusted execution claim is made. Docker's isolation is not a security guarantee against hostile code.

## Audit and limits
SQLite ledger is append-only through API; direct database administrators can rewrite it. `GET /ledger` permits exporting the chain and anchoring the final hash outside SQLite (manual step). The image registry digest is resolved at execution time and recorded; exact replay reproducibility requires pinning image digests and source snapshot content, and stable external dependencies. This implementation stores source snapshots but does **not** yet enforce content-addressed snapshot integrity or durable job requeue after process crashes. SQLite concurrency and job state are single-process only. Not a distributed consensus engine.

## Acceptance status
Source code and sample projects are included. Real Docker sandbox, timeout, failure recovery, and acceptance tests **must be executed on a machine with Docker and .NET**. Production security review, API auth, daemon access isolation, restart recovery, DB migrations, and CI remain pending.


See docs/PATCH_v0.1.1.md for v0.1.1 changes and required image pinning.


## Reliability patch (unverified .NET build)
- SQLite conditional atomic job claim; queued jobs remain durable.
- On startup, inspect/remove known job-named orphan Docker containers before requeueing interrupted jobs; fail closed if Docker is unavailable. This is NOT a fully crash-atomic Docker/container ownership protocol.
- Complete() inserts verification ledger record and final job state in one SQLite transaction.
- Bounded streaming file copies and rejection of detected links. This does NOT eliminate symlink TOCTOU attacks; only trusted project directories are supported.
- Do not expose API beyond loopback. A local process can still call it; there is no authentication.
- Unresolved: strict disk quotas, external ledger anchoring, robust Docker orphan ownership/reconciliation, crash-fault integration tests, native .NET build verification.
- This patch is a candidate for local testing, NOT production-ready.
