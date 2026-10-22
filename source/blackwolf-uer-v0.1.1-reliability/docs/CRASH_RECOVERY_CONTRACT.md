# UER v0.1.1 — Crash Recovery Implementation Candidate

This source patch is **not release-approved**. It has not been compiled with .NET 8 or run with Docker in the available environment.

## Implemented source changes
- Atomic SQLite job claim + attempt registration with attempt_id, monotonic execution_epoch and preselected container name.
- Conditional attempt fencing on completion; ledger append and final status are one transaction.
- Docker labels for job_id, attempt_id and execution_epoch.
- Container reconciliation on service startup using attempt labels and preselected name; Docker errors quarantine rather than requeue.
- Shutdown cancellation quarantines the attempt. Docker cleanup is best-effort; failure blocks finalization.
- Replay only accepts terminal passed/failed jobs.

## Critical limitations / acceptance blockers
- CRASH-RECOVERY-001/002, STALE-RESULT-001, ATOMIC-CLAIM-001, LEDGER-INTEGRITY-001 and DOCKER-UNAVAILABLE-001 have **not been executed** end-to-end.
- No .NET build or Docker integration has been performed here; C# compilation is unverified.
- Docker daemon availability and an empty `docker ps` do not prove that detached descendants, external side effects or another host's workers have stopped. Use trusted local projects only.
- No multi-process leadership lock: this MVP assumes a single UER service and one local Docker daemon. Starting multiple UER instances against the same DB is outside the safety model.
- A SIGKILL between a Docker create request and container visibility can require manual reconciliation. Do not claim exactly-once semantics.
- Existing project source-copy TOCTOU, hard disk quotas, authentication, external ledger anchoring and adversarial code isolation remain unaddressed.
- Schema changes are additive for the supplied candidate; backup SQLite before upgrading. A production migration/versioning strategy is not implemented.

## Required acceptance procedure
1. Install .NET 8 SDK and Docker; run `dotnet build src/Uer.Api/Uer.Api.csproj`.
2. Set trusted, immutable Docker image references (`UER_PYTHON_IMAGE` / `UER_NODE_IMAGE` to `repository@sha256:digest`).
3. Execute both sample jobs and check terminal state and `/ledger/verify`.
4. Inject SIGKILL during Docker execution and immediately after container creation; restart service and verify no overlapping containers.
5. Force Docker unavailability at startup and confirm `quarantined`, not `queued`.
6. Attempt stale epoch result updates and simultaneous job claims; verify neither can succeed.
7. Record evidence (logs, process IDs, Docker inspect, SQLite snapshots) before considering approval.
