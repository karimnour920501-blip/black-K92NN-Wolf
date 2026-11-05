# Azure deployment design — ZERO-SPEND GATE

Status: DESIGN_ONLY. No Azure resources created. No production deploy performed.

## Baseline
- Existing source: `csharp/BlackWolf.Api` (ASP.NET Core 8).
- Existing CI: `.github/workflows/blackwolf-csharp-ci.yml`; successful CI is not a production approval.
- Target (future, subject to explicit authorization): Azure Container Apps Consumption, managed identity, Key Vault, external durable PostgreSQL.
- No database is provisioned in this phase. The API requires BLACKWOLF_DB and BLACKWOLF_ADMIN_TOKEN; it cannot become ready without PostgreSQL.
- Container Apps free grant is not a hard cost cap. Container Apps environment, image registry, networking, log storage, Key Vault and managed PostgreSQL may incur charges.

## Trust boundaries
1. GitHub Actions -> Entra ID: OIDC federated credential scoped to the exact repository and protected GitHub environment, no long-lived Azure client secret.
2. Deployment identity: resource-group-scoped minimum roles only. No subscription-wide Owner/Contributor as a convenience default.
3. Container App -> Key Vault: system-assigned managed identity + Key Vault Secrets User scoped to required vault/secrets.
4. Runtime -> PostgreSQL: separate database principal with minimal grants; credentials supplied by Key Vault reference. TLS required.
5. Runtime -> OpenAI: not enabled. Future credentials must live in Key Vault, never in source or workflow logs.

## Safe deployment prerequisites
- Confirm an existing Azure tenant/subscription and subscription ownership.
- Review subscription billing status and Azure Policy. Budget alerts are NOT hard spending limits.
- Approve an itemized maximum-cost architecture before creating any resources.
- Provision a protected GitHub environment named `azure-production` with required reviewers and restricted branches.
- Configure OIDC subject for that environment and grant scoped RBAC.
- Configure immutable image digest, private or authorized registry, vulnerability scanning, HTTPS and ingress restrictions.
- Replace bootstrap shared admin token with Entra ID JWT validation and RBAC before public access.
- Set up durable PostgreSQL, backups, restore tests, observability retention limits and rollback.
- Prove smoke/integration tests and review evidence before any production deployment.

## Azure read-only inventory (run locally AFTER signing in; no resources created)
```bash
az account show --query '{name:name,id:id,tenantId:tenantId,state:state}' -o json
az account list --query '[].{name:name,id:id,state:state,isDefault:isDefault}' -o table
az group list --query '[].{name:name,location:location}' -o table
az containerapp list --query '[].{name:name,resourceGroup:resourceGroup,location:location}' -o table
az keyvault list --query '[].{name:name,resourceGroup:resourceGroup}' -o table
```
Never paste access tokens, connection strings or Key Vault secret values.

## References
- https://learn.microsoft.com/en-us/azure/container-apps/billing
- https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect
- https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets
