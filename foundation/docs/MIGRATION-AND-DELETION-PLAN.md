# Migration and deletion review plan

1. Inventory all branches, tags, workflows, issues, releases and dependencies in the legacy repository.
2. Make and verify a full Git mirror backup and separate exports of issues, releases and Actions artifacts as needed.
3. Review for exposed credentials and rotate any affected secrets.
4. Validate the new foundation in CI and migrate only reviewed, tested components.
5. Confirm all downstream references and integrations have moved.
6. Obtain explicit separate approval for deletion. **Do not delete the old repository during this migration.**

Status: review only. Backup, production readiness, and deletion are **not** complete.
