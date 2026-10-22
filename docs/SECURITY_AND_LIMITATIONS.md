# Security boundaries and residual risks

* Docker CLI + Docker daemon on a developer/production host are powerful. Run untrusted
  candidate execution on a single-purpose disposable VM/host with no privileged secrets.
  Do NOT mount a developer's Docker socket or production credentials.
* Name plus labels prevent casual mis-deletion; no Docker CLI sequence is fully
  transactional with SQLite. Race conditions between inspect/remove and daemon compromise
  require a stronger broker/attestation architecture in a future version.
* `container_absence_verified` is a local observation by Runner, **not** externally signed
  attestable evidence. It does NOT prove lack of prior external side effects.
* `RecordCleanupEvidence()` is an internal storage API and can be called in-process; it is
  not remote-proof Docker attestation.
* SQLite remains a single-process database; cross-process fencing not implemented.
* Lifecycle and ledger chains are SHA-256 local chains, not signatures anchored externally.
  A malicious host/DB administrator can rewrite all rows and hashes.
* A restored dump without trust anchors cannot prove absence of omission or wholesale
  replacement. Runtime replay guarantees remain limited.
* Source copy has acknowledged symlink/TOCTOU risks; not suitable for hostile multi-tenant
  input on a shared host.
* Loopback restriction is not user auth, do not expose UER API publicly.
* Docker network none blocks ordinary network access but is not a full security boundary.
* dotnet build, C# store contracts, Docker, acceptance and crash tests have NOT RUN here.

## Patch-specific behavior
- Before removal, `ContainerPresent()` checks the reserved name AND the attempt label
  and verifies job_id, attempt_id, epoch and blackwolf.uer via docker inspect.
- After removal it repeats inspection; ambiguous daemon errors lead to quarantine.
- Final `Store.Complete()` refuses to write passed/failed ledger without exactly one
  cleanup-observation lifecycle event for the fenced attempt.
- `Runner.Execute()` quarantines on missing logs/wait/cleanup evidence and does NOT record
  a normal failed terminal state in those cases.
- Startup reconciliation uses the same identity verification and never automatically
  retries unknown external effects.
- If quarantine persistence fails, worker fails rather than continuing to process jobs.
