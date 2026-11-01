# BLACKWOLF AI — secret-safe OpenAI connection and governance

## Recovered operational design

Local preview: browser UI -> same-origin `POST /api/chat` -> stdlib Python gateway -> OpenAI Responses API -> browser. The live paid API probe is a separate manual-only GitHub workflow (not an automatic backend deployment).

- `OPENAI_API_KEY`: secret server-side variable only, never client-side/mobile, never Git. GitHub Actions smoke uses Environment **`openai-live-test`** and `${{ secrets.OPENAI_API_KEY }}`.
- `OPENAI_PROJECT_ID`: optional project selection metadata. PR #34 proposes pinning the intended project and offline preflight, but **has not been merged**.
- `BLACKWOLF_ACCESS_TOKEN`: separate random local preview access token. It does not implement OAuth/OIDC/JWT/RBAC or production multi-tenant auth.
- `OPENAI_MODEL`: currently defaults to `gpt-6-luna` **as a source-code setting**; model availability and account access are only established by a successful authenticated live call.
- `store:false` for the Responses request; body/history size limits, in-process 10/min limiter, local bind only. Do not describe these as full perimeter, tenant, distributed rate limits, or data retention governance.

## Verified historical failures and recovery

| Evidence | Result | Conclusion |
| --- | --- | --- |
| [Run #2](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41256423787) | `OPENAI_API_KEY is not configured` / exit 2 | The secret was absent from that run. |
| [Run #7](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41260244201) | `http_401` / exit 1 | HTTP call reached OpenAI but auth was rejected. |
| [Run #8](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41260244598) | `http_401` / exit 1 | Same; project-ID-only change is insufficient proof of valid key. |
| [Run #9](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41262032585) | skipped | Trigger confirmation did not pass; not a provider test. |

**No successful live provider response has been verified.** The fact that `secrets.OPENAI_API_KEY` resolves non-empty is not proof that it is a valid full API secret, belongs to the correct project or has a budget/permissions.

## Secure recovery procedure (user-controlled only)

1. In OpenAI Platform choose the exact intended API organization/project, inspect key *name* but never copy its secret into chat or GitHub source.
2. If the full original key value is unavailable, create a replacement scoped to that project using the OpenAI Platform secure UI; store it immediately using GitHub **Environment secrets** in `openai-live-test` as `OPENAI_API_KEY`, rather than Environment variables. Remove any previously exposed value.
3. If approval/reviewer restrictions are configured for the environment, satisfy them before the run; a secret may be unavailable to unapproved jobs.
4. Review the proposed **PR #34** and its offline preflight checks independently. **Do not** merge or rerun merely because the public project ID appears in YAML.
5. Only after confirming a valid full secret and appropriate spending limit, run manual workflow on `main`, enter **exact** `YES_ONE_LIVE_OPENAI_CALL`. It sends one potentially paid provider request. Inspect a sanitized success/error only.
6. A GitHub Actions success would verify one runner. It does NOT configure Hetzner or any actual running service. Configure production backend secrets through its own secret manager, then verify TLS/IAM/budget/audit and monitor before external exposure.

## Release security non-negotiables

- Never put `OPENAI_API_KEY` in web/mobile HTML, React Native `.env` shipped to app bundle, build artifacts, pull request comments or screenshots.
- Do not use `pull_request_target`, automatic PR comments or `push` workflows to access production secrets or call paid providers.
- Keep provider smoke workflow `workflow_dispatch` only with explicit confirmation and minimal `contents:read` permission.
- Backend must implement actual issuer/audience/signature/expiry JWT validation, server-side tenant/RBAC enforcement, idempotent commands, distributed throttling and traceable audit events before production.
- Redact Authorization, tenant data, customer prompts and provider response bodies from CI logs. Treat any externally exposed key as compromised and rotate via provider UI.

## Open questions backed by current evidence

- Is the GitHub Environment `openai-live-test` secret currently a complete key (not masked display text or key ID)? **Not directly readable via GitHub connector.**
- Does that key belong to the intended OpenAI project? **Not verified.**
- Has a successful billable Responses API request been observed? **No.**
- Is the local Python gateway production-deployable directly? **No; preview only**.
