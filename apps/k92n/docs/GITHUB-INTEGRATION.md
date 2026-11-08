# GitHub hosting integration

Added as apps/k92n in black-K92NN-Wolf without modifying existing applications.
Root render.yaml uses apps/k92n as Docker build context. Module source remains identical to K92N 1.0.1; hosting files derive from Hosting Ready 1.0.0.

Prior evidence files record local checks and keep their original scope. The new workflow adds actual Docker build + disposable volume tests; its existence is NOT a passing result. docker-ci-results.json is produced only when that test executes. Ownership initialization in CI applies only to a disposable test volume; it does not establish Render disk permissions.

No secret, production database, self-contained binary, or cache is committed. No deploy job is configured. PRODUCTION_READY remains FALSE. Render billing approval and workspace confirmation are separate from this GitHub change.
