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
