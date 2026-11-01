# BLACK-K92N-WOLF — MASTER RECONSTRUCTION

**Date:** 2026-11-01. **Branch:** `rebuild/black-k92n-wolf-unified-20261101`.
**Status: ENGINEERING RECONSTRUCTION / NOT PRODUCTION.**

## Source-of-truth policy

This work reconstructs the **current conversation's** GitHub / OpenAI / Mobile S1–S6 work without mixing speculative requirements into production claims. All destructive changes and merges to `main` require separately explicit owner approval. Do not copy provider credentials into source, actions comments, chats, mobile JS, or artifacts.

### Verified source baselines

| Subsystem | Canonical location | Baseline | Evidence |
| --- | --- | --- | --- |
| BLACKWOLF AI web/chat + secure localhost Python gateway | `main`, `apps/blackwolf-ai` | `9ab3ad4ed2f6c94bb814947ed9ac1eb4e4bd8050` | PR #31 merged; CI 21 Python + 3 Node tests; Pyright 0 errors |
| BLACKWOLF AI live API probe | `main`, `.github/workflows/blackwolf-openai-live-smoke.yml` | same `main` SHA | manual workflow only; **not successfully authenticated** |
| Expo Mobile MVP v1.0, S1 shell | `development/mobile-mvp-s1-evidence` | `a5f16ae704e659dcc47daddba45b561217750121` (baseline tree) | S1 CI 40996051123 PASS, Metro/TS/tests only |
| Mobile S6 evidence and preview guards | `development/mobile-mvp-s6-evidence-gate-20261101` | `a4ca99bfb1f343e30f3dc9faf349236a44a9e847` | PR #32 draft; 17 mobile tests + 7 policy tests; dependency scan still failed |
| OpenAI project-scoping and offline key preflight proposal | PR #34 (unmerged) | review PR #34 head before use | Cannot repair HTTP 401 merely by adding project ID |

### Partial copy into this reconstruction branch

This branch starts from Mobile S6 and imports the current `main` Python OpenAI gateway, backend tests, smoke script, and workflow. The original `apps/blackwolf-ai/index.html` **was not imported**: the GitHub connector blocked its copy during reconstruction. The authoritative web UI remains available on `main` at its existing path. **Do not claim this branch is a complete runnable unified web/mobile build until that file is restored through an authorized review workflow and all tests run.** It is a preparation branch, not an approved merger. Other imported paths retain their source blob hashes for comparison.

### Repository map

- `apps/blackwolf-ai` — Python standard-library local-only HTTP server, static web UI **on main**, Responses API adapter, offline mocks and manual provider smoke check.
- `BLACK-K92N-WOLF-Mobile-MVP-v1.0-S1` — Expo SDK 54/React Native/TypeScript five-tab demo shell (S1 scope), source-only lint; not authenticated.
- `mobile/s6` — E2E-01..08 matrix, 26 pending release evidence gates, audit triage and release status.
- `.github/workflows` — independent offline CI, manual-only live OpenAI test, S1/S6 CI and guarded manual EAS builds.
- `components/control-plane`, `components/runtime`, `source/blackwolf-uer-v0.1.1-reliability` — existing separate runtime / recovered UER code; not evidence that multi-region Tier-1 architecture is deployed.
- `db`, `src/Wolf.Commands.Api`, `tests` — V2.1/commands / security contract source in the mobile branch; functionality must be verified at relevant test and deployment levels.

### Verification of prior steps (real GitHub)

- PR #28: initial local BLACKWOLF AI backend and UI merged into `automation/hetzner-staging-connection-20261031`, **not** directly to `main`.
- PR #29: Codex P2 fixes for history size, UTF-8 byte limits and IPv6; merged into Hetzner branch. Pyright 1.1.414 caught and fixed `log_message` override signature.
- PR #30: manual live OpenAI probe, original stacked PR still open and unmerged; canonical probe already reached `main` via clean PR #31.
- PR #31: **merged into `main`** at SHA `9ab3ad4ed2f6c94bb814947ed9ac1eb4e4bd8050`; contains only the original BLACKWOLF AI integration.
- PR #32: draft Mobile S6 release evidence and preview CI **not merged**. Release remains blocked.
- PR #34: draft OpenAI project-id + key preflight fix **not merged**. Earlier live attempts reached HTTP 401; no successful Responses output proved.

### Operational boundary

**Implemented in source** is different from **passed offline CI**, **passed live provider call**, **native build**, **device E2E**, **staging**, and **production**. The last four have not been demonstrated for Mobile v1.0. Provider key may be readable by GitHub runner but rejected by OpenAI (HTTP 401). Browser/local access token is not production identity. Backend JWT/RBAC/tenant isolation are still required for the mobile product.

See [OPENAI-AND-SECURITY.md](OPENAI-AND-SECURITY.md), [MOBILE-S6.md](MOBILE-S6.md), and [EVIDENCE.json](EVIDENCE.json).

**Approval rule:** no automatic merge to `main`, production deploy, external paid cloud build, provider key rotation or live API invocation in this reconstruction step.