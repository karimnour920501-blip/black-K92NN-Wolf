# BLACKWOLF AI — local verified-code preview (NOT production)

This is a new, isolated chat page for BLACK-K92N-WOLF. It **does not** alter the existing Control Plane, Runtime, audit/event models, workflows, or production infrastructure. It uses the OpenAI **Responses API** through a Python backend. It does not need the beta Agents API for a basic text chat.

## Requirements

- Python 3.10+; no third-party Python packages.
- A project-scoped OpenAI API key with suitable model permissions, **configured in the backend only**.
- A local, independent BLACKWOLF_ACCESS_TOKEN (min. 32 characters) that **is not your OpenAI key**.

To configure from a trusted terminal, set OPENAI_API_KEY to your project secret, and generate a separate local access token with:

    export BLACKWOLF_ACCESS_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export OPENAI_MODEL='gpt-6-luna'
    python server.py

The OPENAI_API_KEY environment variable must also be configured securely in the backend environment before starting. Optional: OPENAI_PROJECT_ID for selecting an OpenAI project.

Open http://127.0.0.1:8787/ and paste the BLACKWOLF_ACCESS_TOKEN into the page's *local access token* field. Do **not** paste the OpenAI API key into the browser. The page stores neither token nor chat history outside its current in-memory session. /api/status reports whether key environment configuration exists; it **does not perform** a live connection check. Send a message to test real API access, billing and model permissions. API calls cost money. An openai_unavailable response can mean invalid model access, no billing, network failure, upstream error or timeout; check server/network configuration without printing secrets.

## Security and scope

- Binds **only to loopback** (127.0.0.1) and refuses public bind addresses. Neither service nor UI is internet-deployable as-is.
- Browser talks only to same-origin /api/chat. OpenAI secret is held only in the backend process. Access-token auth, strict JSON/body/history limits, process-local 10 requests/min rate control and nonpersistent Responses requests (store:false).
- The access token is a **local preview guard**, not full production IAM. Production requires TLS, user authentication, tenant isolation, distributed rate limiting, request quotas, audit policy, abuse detection, monitoring and a cost budget.
- No automatic GitHub writes, workflow runs, deployments, account changes, key rotation, provider account connections or external agent actions.
- Existing source folders are retained pending evidence-based cleanup and review.

## Tests

Run from apps/blackwolf-ai:

    python -m unittest discover -s tests -v

These tests use a mocked provider and local HTTP server. **They do not prove live OpenAI connectivity, GitHub Actions success or production readiness.**


## One-request LIVE OpenAI connection test (manual and opt-in)

The repository includes [verify_openai.py](verify_openai.py) and
[blackwolf-openai-live-smoke.yml](../../.github/workflows/blackwolf-openai-live-smoke.yml).
**A paid real API request is made only when explicitly triggered.** Normal CI tests
use a mocked provider. This test does not create Agents API resources, enable
provider plugins, deploy a server, or modify OpenAI account settings.

To prepare using the GitHub web UI (including on iPhone):

1. Finish creating or selecting a project-scoped OpenAI API key with
   Responses write permission, access to the model and a usage budget. Never
   send the key in chat, a PR, an issue or source code.
2. Review and merge prerequisite BLACKWOLF AI branches and this workflow
   into the repository default branch when approved. GitHub Run workflow
   normally requires the workflow file to exist on the default branch.
3. Repository Settings → Environments → New environment: create
   openai-live-test. Add required reviewers if available. In its environment
   secrets, add a secret named OPENAI_API_KEY with the real secret value.
   Optionally add OPENAI_PROJECT_ID as an environment secret.
4. Repository Actions → BLACKWOLF OpenAI live connectivity (manual only)
   → Run workflow. Enter YES_ONE_LIVE_OPENAI_CALL to confirm one paid request.
5. Examine the workflow run: only a successful
   "OpenAI connection VERIFIED" result establishes that the GitHub runner
   received the expected response from OpenAI.

To run the same check from a trusted server terminal where OPENAI_API_KEY
has been securely configured:

    cd apps/blackwolf-ai
    OPENAI_MODEL=gpt-6-luna python -B verify_openai.py

The script sends a single request to POST /v1/responses with
max_output_tokens=64, reasoning.effort=none (for GPT-6 Luna), and store=false.
It prints only a status marker, not the credential, API response, or prompt.
HTTP 401/403 usually indicates key or authorization issues; HTTP 429 may
indicate usage or rate limits.

### Selected BLACKWOLF live-test project and 401 recovery

The manual smoke workflow on the review branch pins OpenAI project
`proj_dvKpPmjuD9RUvEe2mYN4noiZ` (Besh oo's project ID is **not** an API key).
The selected credential should be the **full, unmasked secret value** for
`BLACKWOLF-OPENAI-LIVE-TEST` from this same project. The key name, `key_...`
tracking ID, `user-...` owner ID, `proj_...` project ID, and screenshot's
`sk-...IGYA` masked view **cannot authenticate**.

The existing GitHub environment `openai-live-test` supplies
`OPENAI_API_KEY`. Update the value inside that environment, which can shadow
a repository-level secret with the same name. If OpenAI no longer shows the
full value, create a replacement key in the same OpenAI project and place
its secret value in the GitHub environment directly. Never paste secret
values into chat, PRs, logs, repo files or a mobile app.

To perform a **local-only validation with no API usage**:

    cd apps/blackwolf-ai
    python -B verify_openai.py --preflight

This catches missing, masked, malformed, or wrong-identifier values but
**cannot verify authenticity or scope**. The manual workflow first runs this
offline preflight and then, only if the preflight succeeds, sends its single
paid Responses API call. A `http_401` still means authentication was
rejected by OpenAI; rotate or correct the project-bound secret rather than
modifying the code or adding the public Project ID to the API key.


**Crucial:** Success from GitHub Actions does not configure OPENAI_API_KEY
on the local page, Hetzner VPS or any other running backend. That
deployment needs its own secure secret configuration and live test.
Do not commit git-tracked .env files or enable automatic paid CI runs.
