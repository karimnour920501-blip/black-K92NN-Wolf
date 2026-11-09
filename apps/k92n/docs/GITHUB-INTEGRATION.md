# GitHub hosting integration

Added as apps/k92n in black-K92NN-Wolf without modifying existing applications.
Root render.yaml uses apps/k92n as Docker build context. The initial imported baseline was K92N 1.0.1 / Hosting Ready 1.0.0. The 1.0.2 pilot adds read-only ledger views, decimal-string HTTP adapters, a mobile operator UI and browser tests. The accounting schema, posting transaction/reversal implementation and hash contract remain unchanged. See PREPAYMENT-PILOT-1.0.2-AR.md.

Prior evidence files record local checks and keep their original scope. The new workflow adds actual Docker build + disposable volume tests; its existence is NOT a passing result. docker-ci-results.json is produced only when that test executes. Ownership initialization in CI applies only to a disposable test volume; it does not establish Render disk permissions.

No secret, production database, self-contained binary, or cache is committed. No deploy job is configured. PRODUCTION_READY remains FALSE. Render billing approval and workspace confirmation are separate from this GitHub change.
