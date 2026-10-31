# BLACK-K92N-WOLF — Hetzner connection gate (iPhone compatible)

## Status and scope

This is a **read-only connection verification** workflow for Hetzner Cloud. It does not provision servers, create firewalls, change SSH, or deploy containers. It must be reviewed and merged to the default branch explicitly before manual dispatch is available.

## 1. Sign in using Safari (never give credentials to ChatGPT)

1. Open https://console.hetzner.com/ and finish account security verification.
2. Open or create a dedicated **staging** project in Hetzner Cloud.
3. Inside that project: `Security` -> `API tokens` -> `Generate API token`.
4. Use a **Read** token for this connectivity test. The token is scoped to the chosen Hetzner project.
5. Copy the token directly to GitHub's secret form. **Never paste it in chat, an issue, a repo file, screenshots, or workflow logs.** Hetzner shows it only once.

## 2. Save the token in GitHub

1. Open the repository's `Settings` -> `Environments` -> create `hetzner-staging`.
2. Configure allowed deployment branches to `main`; optionally require approval of environment jobs.
3. Open `hetzner-staging` -> `Environment secrets` -> `Add secret`.
4. Set name `HCLOUD_TOKEN` and paste the token value. Do not use a plain repository variable.

## 3. Run the explicit API verification

1. Review the PR containing `.github/workflows/hetzner-connection-check.yml`.
2. Merge only after approval. Do not merge this preparatory branch automatically.
3. Open `Actions` -> `Verify Hetzner Cloud connection` -> `Run workflow` on `main`.
4. A successful job reports `Hetzner API is reachable and the project token is valid`. It does **not** mean a VPS exists or a deployment works.

## 4. Follow-on provisioning gate (not implemented by this PR)

After the connection check passes, approve a separate infrastructure change that specifies server type, region, budget and SSH public key, and creates a Hetzner Cloud Firewall **before** attaching a public network. Provisioning needs a separate **Read & Write** Hetzner token stored in a protected GitHub Environment secret, ideally named `HCLOUD_PROVISION_TOKEN`, not the read-only verification token. Never expose PostgreSQL/Redis ports.

After creating a fresh Ubuntu 24.04 VPS, use the separately prepared staging package for Docker Engine, UFW, Fail2ban, private-network PostgreSQL 16 and Redis 7 with `noeviction`; test new SSH login before changing any SSH hardening.

## References

- Hetzner: https://docs.hetzner.com/cloud/api/getting-started/generating-api-token/
- GitHub: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- GitHub manual run: https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow
