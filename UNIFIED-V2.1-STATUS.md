# BLACK-K92N-WOLF Unified Platform v2.1 — CI Candidate

Status: **SOURCE VERIFIED / DOTNET BUILD NOT VERIFIED / POSTGRESQL INTEGRATION NOT VERIFIED**.

This branch is reserved for the v2.1 candidate. The full source bundle has **not** yet been uploaded to this branch. Do not merge this branch until the ASP.NET Core 10 application, migrations, and tests are committed and GitHub Actions succeeds.

Scope: shared command runtime, tenant-scoped projects, JWT/RBAC, PostgreSQL RLS, evidence logging, and CI.

Security: never use the migration owner or postgres superuser as the application role; do not commit JWT signing keys or database passwords.
