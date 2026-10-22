# UER v0.1.1 P0 Fail-Closed Recovery Source Patch

## Behavior
- RecoveryPolicy.EvaluateRecovery returns VerifiedCompletion only with an explicit verified completion flag; SafeToRetry requires termination and retry-safety evidence.
- The current Worker has **no trusted evidence provider**, so startup reconciliation always selects InsufficientEvidence and QUARANTINED, even if the old container is absent or removed.
- Store.Reconcile performs fenced job/attempt updates and appends a hash-chained recovery_audit row in one SQLite transaction.
- MarkRunning and Complete now enforce row counts for both job and attempt.
- Process cancellation distinguishes service shutdown from timeout.

## Important limits
- This is deliberately conservative: there is no automatic recovery retry, nor an implemented trusted completion attestation. SafeToRetry and VerifiedCompletion are policy states only; callers MUST NOT supply unverified booleans.
- recovery_audit is an internal hash chain, not externally anchored. The existing ledger tracks final results separately.
- .NET compilation, Docker tests, crash tests and security acceptance are NOT VERIFIED.
- Container disappearance is NOT proof of no external effects. No exactly-once guarantee.
- An already-quarantined attempt remains quarantined on subsequent startups. Operator adjudication is not implemented.
