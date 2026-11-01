# BLACK-K92N-WOLF — OpenAI Integration Master Rebuild

**Date:** 2026-11-01  
**Scope:** Exact reconstruction of the OpenAI API / GitHub integration thread and its verified repository state.  
**Repository:** [karimnour920501-blip/black-K92NN-Wolf](https://github.com/karimnour920501-blip/black-K92NN-Wolf)  
**Review branch:** `fix/blackwolf-openai-project-id-20261101`  
**Review PR:** [#34](https://github.com/karimnour920501-blip/black-K92NN-Wolf/pull/34) — draft, not merged  
**Status:** Offline/CI source checks pass; live OpenAI connection **NOT VERIFIED**.

> This record distinguishes design, implemented source, offline tests, GitHub CI, live provider connectivity, and production deployment. It includes **no credential values**. Key names and identifiers are metadata, not authentication secrets.

## 1. Intended result

Build a BLACKWOLF AI backend that can call OpenAI Responses API using a project-scoped credential, with:

- A single manually authorized and potentially billable smoke call to `POST https://api.openai.com/v1/responses`.
- API key held exclusively on a trusted server or GitHub Actions environment, never in frontend, repository, screenshot, PR, or chat.
- Offline tests plus a local-only credential-shape preflight before any live call.
- A deterministic success marker (`BLACKWOLF_OPENAI_OK`) and safe failure classification without logging provider response bodies.
- No automatic paid run, merge to `main`, public production deployment, or false assertion of successful connection.

## 2. Chronology — from first workflow link to current state

1. The conversation began with the link to `.github/workflows/blackwolf-openai-live-smoke.yml` in the repository. The workflow was found on `main`, already configured for manual `workflow_dispatch` with explicit confirmation `YES_ONE_LIVE_OPENAI_CALL`, GitHub environment `openai-live-test`, Python 3.13, model `gpt-6-luna`, and a read-only token policy.
2. Early GitHub Actions runs were skipped, failed to start, or failed. In the first fully diagnosed failure, the runner printed `OPENAI_API_KEY is not configured` and exited with status 2. The secret had not reached the probe.
3. Later runs #7 and #8 did receive an environment value for `OPENAI_API_KEY` (GitHub masked it as `***`) but got HTTP `401` from OpenAI. In run #8, this occurred at `2026-11-01T01:14:46Z`. This shows the API rejected authentication, **not** that the model was unavailable or the connection worked.
4. Project and owner identifiers were supplied in the conversation. A separate `Default project` ID `proj_ZZ00Mkgewlzx96wvKcP9Tczr` was discussed, but the selected Besh oo project for BLACKWOLF integration is **`proj_dvKpPmjuD9RUvEe2mYN4noiZ`**. These are different projects; do not mix keys or IDs.
5. Three Besh oo project API key records were supplied through account screenshots: `Secret` (user owner), `BLACKWOLF` (service account), and `BLACKWOLF-OPENAI-LIVE-TEST` (service account). All showed `Active` and `Last used: Never` **at the moment of those screenshots**. The screenshot values shown as `sk-...` were masked and are **not full API keys**.
6. A review branch was created: `fix/blackwolf-openai-project-id-20261101`. PR #34 was opened as a **draft**, based on `main`. The workflow now pins the selected project ID (metadata, not secret).
7. The Python probe was updated to validate missing, malformed, masked, and wrong-type IDs in an offline `--preflight` mode. A sanitized 401 recovery message was added. Six additional tests were committed, bringing `test_verify_openai.py` to **11** tests.
8. The manual workflow was changed to run `python -B verify_openai.py --preflight` before `python -B verify_openai.py`. Failed preflight exits without paid API use.
9. The application README was updated with the selected project, secure environment-secret handling, 401 recovery, and the distinction between offline and live verification.
10. On the last code/docs commit before this master record (`a576e15832a795f785d7504f14d6c03504bde01d`), GitHub Actions succeeded:
    - [BLACKWOLF AI preview isolated tests, run 41262394746](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41262394746): **success**. Pyright `0 errors, 0 warnings, 0 informations`; **27 Python tests passed**, including 11 for `verify_openai.py`; browser client tests succeeded.
    - [UER P1 source build, run 41262394764](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41262394764): **success**. This is a source/build contract check, not production approval.
11. The latest observed manual live smoke run was [#9, 41262032585](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41262032585): **skipped**. Earlier runs [#8](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41260244598) and [#7](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41260244201) **failed**. No successful live OpenAI connection has been established.

## 3. Project/key mapping

| Field | Agreed intended value | Interpretation |
|---|---|---|
| Repository | `karimnour920501-blip/black-K92NN-Wolf` | Source of implementation |
| Selected OpenAI project | `proj_dvKpPmjuD9RUvEe2mYN4noiZ` | Besh oo project, non-secret identifier |
| Separate earlier default project | `proj_ZZ00Mkgewlzx96wvKcP9Tczr` | **Do not mix** with the selected project |
| Key record for manual test | `BLACKWOLF-OPENAI-LIVE-TEST` | Key label, **not its value** |
| Other key records | `BLACKWOLF`, `Secret` | Separate records; keep distinct |
| GitHub environment | `openai-live-test` | Scope in which the Actions job runs |
| Secret name | `OPENAI_API_KEY` | Must contain the **full** OpenAI API secret |
| Project header | `OPENAI_PROJECT_ID` | Currently pinned in review-branch workflow |
| Model in code | `gpt-6-luna` | Configured model, live entitlement unverified |
| Manual confirmation | `YES_ONE_LIVE_OPENAI_CALL` | Exact opt-in string |
| Success marker | `BLACKWOLF_OPENAI_OK` | Probe's expected model text |

Security boundary: `user-...` owner IDs, `key_...` tracking IDs, `proj_...` project IDs, and masked `sk-...` screenshot fragments cannot substitute for the full secret value. A key being `Active` does not guarantee the GitHub secret is the same usable value or that it has been granted access. A GitHub environment secret can take precedence over a repository secret of the same name.

## 4. Implemented structure

```text
.github/
  workflows/
    blackwolf-openai-live-smoke.yml   # explicit manual opt-in, no deployment
    blackwolf-ai-preview-tests.yml    # offline CI
apps/
  blackwolf-ai/
    server.py                          # local-only HTTP chat backend
    index.html                         # browser client
    verify_openai.py                   # offline preflight + one-request live probe
    tests/
      test_verify_openai.py           # 11 offline probe tests
      test_server.py                  # backend & HTTP tests
      test_client.cjs                # browser client tests
    README.md                          # security and usage documentation
docs/
  BLACKWOLF-OPENAI-MASTER-REBUILD-2026-11-01.md
```

**Backend behavior currently in source:** Python standard-library server binds to loopback; serves chat UI and `/api/chat`, `/api/status`, `/health`; uses a separate local `BLACKWOLF_ACCESS_TOKEN` for the preview; sends Responses API requests server-side with `store:false`; validates request input, imposes local rate limits, and does not return the OpenAI key to the browser. This is a **local preview**, not a public internet SaaS gateway.

**Live probe behavior:** Sends `POST /v1/responses` with `max_output_tokens:64`, `reasoning.effort:none`, `store:false`; searches the response for the exact success token and logs no model output. HTTP error bodies are not printed.

**Offline preflight behavior:** Checks existence/shape of key, model, and project ID. It does **not** validate cryptographic authenticity, model access, billing, quota, or actual OpenAI connectivity.

## 5. Changes on review branch (prior to this record)

| File | Change |
|---|---|
| `.github/workflows/blackwolf-openai-live-smoke.yml` | Pin selected project and require offline preflight before the manual single-call probe |
| `apps/blackwolf-ai/verify_openai.py` | Shape checks, `--preflight`, sanitized 401 recovery |
| `apps/blackwolf-ai/tests/test_verify_openai.py` | Add 6 offline tests to existing 5 |
| `apps/blackwolf-ai/README.md` | Correct project, secret locations, runbook and verification limits |

Evidence commits (in sequence): `397b494b5746372980b34464892561ec38d310ba`, `3c4fecf8fab9dfafbc28fa88c22e24e0baafe181`, `7db144851d27fa8ac776c9a1357de5503b5d48e5`, `707614fd32546f74ea0841411be85d9bdd9c7777`, `a576e15832a795f785d7504f14d6c03504bde01d`.

## 6. Evidence matrix / acceptance criteria

| Gate | Status | Basis |
|---|---|---|
| Workflow and source exist | **Verified** | Repo files and PR #34 |
| Offline preflight implemented | **Verified in source + CI** | `verify_openai.py`, test suite |
| 11 probe tests pass | **Verified** | Run 41262394746 |
| Full Python test suite passes | **Verified: 27/27** | Run 41262394746 |
| Pyright type check | **Verified: 0 errors/0 warnings** | Run 41262394746 |
| Browser client tests | **Verified** | Run 41262394746 |
| UER source build | **Verified** | Run 41262394764 |
| Live OpenAI API accepts current key | **NOT VERIFIED** | HTTP 401 in #7/#8; #9 skipped |
| Actual key value in GitHub environment | **Unverified** | Secret values unavailable through connected GitHub tools |
| Model/billing permissions | **Unverified** | Requires successful authorized provider call |
| Public backend deployment | **Not implemented/verified by this change** | Local-only server and no deploy steps |
| Merged to `main` | **No** | Draft PR #34, no merge |
| Production readiness | **No** | Multiple unmet controls |

## 7. Exact remaining operations and ownership boundary

1. In the OpenAI Platform, use a full project-scoped secret from the **selected** project. If its full value is no longer retrievable, generate a new key for the project (ideally a dedicated service account credential) with suitable Responses API permissions, then retire obsolete keys when safe.
2. On GitHub, open `Settings → Environments → openai-live-test → Environment secrets`; set **`OPENAI_API_KEY`** to that complete secret. Verify an older environment value is not shadowing the repository-level one. Do **not** upload screenshots with unmasked keys.
3. Review PR #34. The branch contains the improved preflight and project binding; no merge is needed merely to inspect code, and there is no blanket merge approval.
4. Use `Actions → BLACKWOLF OpenAI live connectivity (manual only) → Run workflow`; select review branch `fix/blackwolf-openai-project-id-20261101` and enter exactly `YES_ONE_LIVE_OPENAI_CALL`. **This authorizes one potentially billable request.**
5. Confirm successful `OpenAI connection VERIFIED` from that exact workflow run before declaring success. On failure, report only sanitized outcome, never secret or provider body.
6. After passing the live gate, configure a **separate trusted backend environment** for `apps/blackwolf-ai/server.py`; GitHub Actions secrets do not configure deployed servers. Prove `/api/chat` with a real request and retain evidence.
7. For public production: add TLS, durable IAM, tenant isolation, distributed quotas, cost budgets, observability, audit policy and deployment/rollback evidence. Do not claim these are delivered by the smoke test.

**Tool access limitations:** Connected GitHub actions can inspect source, create commits/branches/PRs and read available CI logs; they do **not** provide secret-value writes or an authorized workflow-dispatch mutation in the current connector. No private key was imported into the repository. No new paid request was initiated through the assistant.

## 8. Definition of done and frozen handoff

- **Source/CI milestone:** complete for the latest checked pre-documentation commit.
- **Live-connectivity milestone:** blocked until an actual full correct key is securely configured and the manual test succeeds.
- **Production milestone:** out of scope, requires a distinct engineering and operational verification process.
- **Branch policy:** keep `main` unchanged until review/explicit approval.
- **Truth discipline:** an `Active` OpenAI key record is account metadata; a passing unit test is not a network call; a GitHub runner test is not a production deployment.

**Next actionable decision:** securely update `OPENAI_API_KEY` in `openai-live-test`, execute precisely one manual live test on the review branch, and record its evidence. Do not repeat source rewrites to treat HTTP 401 as a solved issue.
