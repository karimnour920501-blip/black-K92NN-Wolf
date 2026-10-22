# UER v0.1.1 — Gate Status

The entire release remains **BLOCKED**. The source package is a proposed hardening patch,
not a proven release or a compatible guarantee.

## Tests with official identifiers (0/10 independently verified)

| Identifier | Scope | Status |
|---|---|---|
| ATOMIC-CLAIM-001 | atomic claim + persistent audit under real UER | NOT_RUN |
| STALE-RESULT-001 | fence old attempt completion | NOT_RUN |
| CRASH-RECOVERY-001 | kill process during Docker create/start | NOT_RUN |
| CRASH-RECOVERY-002 | restart after interruption, inspect orphan handling | NOT_RUN |
| DOCKER-UNAVAILABLE-001 | Docker daemon outage/CLI error must fail closed | NOT_RUN |
| LEDGER-INTEGRITY-001 | tamper detection + ledger verification via live API | NOT_RUN |
| EXTERNAL-EFFECT-001 | evidence of external effects and safe replay policy | NOT_RUN |
| CONTAINER-CREATED-001 | create/start lifecycle split under actual Docker | NOT_RUN |
| QUARANTINE-IDEMPOTENCY-001 | repeated restart cannot release quarantine | NOT_RUN |
| RECOVERY-AUDIT-001 | recovery audit content + tamper detection | NOT_RUN |

## Additional independent P1 control gates (0/3)
- Lifecycle audit completeness — SOURCE_PATCH_CREATED, behavior **NOT_RUN**.
- Cleanup failure paths — SOURCE_PATCH_CREATED, Docker fault test **NOT_RUN**.
- Docker crash recovery — SOURCE_PATCH_CREATED, actual fault tests **NOT_RUN**.

## Acceptance evidence
- Build console logs + exit code and target .NET 8 runtime.
- Independent tests must run in isolated disposable VM with private Docker daemon.
- Capture UER SQLite DB before/after crash, logical job/attempt/audit snapshots, Docker inspect/ps
  results, unique job IDs and attempt IDs, timestamps, outcome for every test.
- Check all 10 IDs exist as explicit PASS, not source token matches.
- Hash all evidence files and archive candidate; all results tied to exact candidate digest.
- Any failed/blocked/missing mandatory test -> release BLOCKED.
- Even 10/10 test passes requires security review, deployment controls, change approval and rollback review.

## Run on a dedicated test host
```bash
python3 -m unittest discover -s verification -v
./scripts/verify_on_isolated_host.sh
```

**Important:** The nine source-level C# store contract tests are additional engineering
checks. They do not count as the ten independently verified Docker acceptance tests.
