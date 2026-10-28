# UER v0.1.1 P1 Source Remediation Candidate

Changes: precommitted attempt_id on jobs, conditional claim/container_created/running transitions, separate Docker create/start/wait, stable quarantine on startup, independent recovery_audit verifier, and fail-closed cleanup.

Important limits:
- NOT built with .NET 8; NOT run against Docker. All 10 acceptance tests remain pending.
- Docker start success does not prove the application started; Docker CLI interruptions are ambiguous and quarantine the attempt.
- Recovery never auto-retries, even if the old container disappears.
- Quarantine is stable across restarts; no automatic re-evaluation.
- Ledger and recovery audit are locally hashed but NOT externally anchored.
- Existing single-process SQLite writer assumption remains. No distributed fencing.
- Lifecycle transitions use atomic updates of jobs/attempts but do not currently append a separate lifecycle event to the recovery_audit table; recovery_audit records recovery decisions only. The requirement for audit of *every* transition remains open if interpreted literally.
- Source copy still has documented TOCTOU limitations; do not treat as secure multi-tenant execution.
- This is a source candidate, NOT an approved release.
