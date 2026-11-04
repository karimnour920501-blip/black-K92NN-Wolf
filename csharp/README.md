# BLACK-K92N-WOLF — C# Control Plane
Owner: Karim Nour

Status: SOURCE ONLY. CI must pass before claiming build/runtime verification.

## Components
ASP.NET Core 8, PostgreSQL 16, Docker Compose, authenticated project registry, read-only server registry and audit endpoint.
No SSH execution, secrets vault, billing, cloud provisioning or production deployment.

## Run
1. Generate and store POSTGRES_PASSWORD and BLACKWOLF_ADMIN_TOKEN outside Git.
2. Set both environment variables; admin token must be at least 32 UTF-8 bytes.
3. Run `docker compose up --build -d` from this directory.
4. Run `bash tests/smoke.sh` with BLACKWOLF_ADMIN_TOKEN exported.

## GitHub Actions
Set repository Actions secrets `CI_POSTGRES_PASSWORD` and `CI_ADMIN_TOKEN` to unique random values. The workflow intentionally fails if they are absent.
Never commit .env or API credentials. The CI only builds and runs local containers, not production deployments.

## Limitations
Single shared admin token is bootstrap-only; replace with identity and RBAC.
Database schema is initialized only for a fresh PostgreSQL volume.
No integration with real VPS, OpenAI, Meta, Shopify, Stripe or Azure.
