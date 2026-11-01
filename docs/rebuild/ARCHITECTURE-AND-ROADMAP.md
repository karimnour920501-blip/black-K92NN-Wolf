# BLACK-K92N-WOLF — unified target architecture (roadmap vs proven source)

**System goal:** a multi-tenant, auditable SaaS integrating C#/.NET APIs, Python AI/decision services, an Expo mobile client, event-driven governance, and protected OpenAI model access.

## Proven vs planned layers

| Layer | Source observed in repository | Present evidence boundary | Target |
| --- | --- | --- | --- |
| Web AI preview | `main/apps/blackwolf-ai` | Local Python HTTP preview, separate local token; mock provider tests, no proven live provider auth | Hardened BFF for multi-tenant users with OIDC/JWT, budgeted OpenAI adapter |
| Mobile | `development/mobile-mvp-s6-evidence-gate-20261101/BLACK-K92N-WOLF-Mobile-MVP-v1.0-S1` | Expo S1 five tabs and source tests; no native builds or real auth | Native Android+iOS client with secure session, tenant switching, E2E and A11y |
| C# commands | `src/Wolf.Commands.Api` on mobile branch | Source code exists; a deployed secure multi-tenant API is not evidenced by file presence | RBAC/idempotency, real command handlers, evidence-producing status |
| UER reliability | `source/blackwolf-uer-v0.1.1-reliability` | Recovered .NET source with SQLite contracts and CI checks | Deterministic orchestration, replay evidence, governance |
| Python runtime / control plane | `components/runtime`, `components/control-plane` | Separate source and unit tests | Operational engine with cost/reliability observability |
| Database | `db/001_init.sql`, `db/002_workspaces.sql` on mobile branch | SQL migrations exist; prod Postgres HA/RLS not confirmed | RLS tenant isolation, append-only audit with causal and replay invariants |
| Messaging/storage/HA | no current end-to-end proof in examined branches | **Architecture goal only** | Kafka cluster, Postgres HA, Redis, distributed locks and multiregion K8s |
| Safety/governance | safety and evidence planning | No operational evidence for OMEGA-CORE-X live integration | Constitutional guards, signed override events, replay & fail-closed gates |

## Reference logical dataflow (target; NOT asserted deployed)

```text
 Expo Android/iOS -----+
                       | OIDC / JWT / TLS / Tenant context (SERVER VALIDATED)
 Web / operator UI ----+--> C# BFF / API gateway --> RBAC / tenant guard / quotas
                                                |
                                                +--> Commands API + idempotency ledger
                                                +--> Projects / Evidence projection
                                                +--> Python AI adapter --> OpenAI Responses API
                                                +--> Event-sourced audit (planned)
                                                        |
                                                        +--> Kafka / replay / OMEGA guard (planned)
                                                        +--> PostgreSQL RLS + Redis (planned)
```

## Nonnegotiable cross-cutting contracts

- Server derives tenant authorization from a validated identity/session and membership, never from a trusted mobile `tenant_id` alone.
- Access tokens/refresh tokens use secure OS storage; do not log, URL-embed, put in GitHub or bundle into mobile. The original local preview bearer token is **not** a replacement for OIDC.
- Mutating endpoints use server-side authorization, idempotency keys, bounded retries and traceable correlation IDs; read retries cannot duplicate side effects.
- Never report a hash chain as `Verified` until independently revalidated through a real backend verifier. No mock evidence labeled production.
- Each event should have immutable stream/tenant/sequence, causation/correlation, replay state hash and retention policy; signatures and HLC only when implemented and tested.
- CI must establish source integrity, unit/contract tests, lint, build, dependency scan, E2E devices, release evidence and human approval in separate gates.
- Provider calls run server-side with protected secrets, per-tenant spend limits, anomaly alerts and minimal PII. Manual smoke test does not bootstrap public deployment.

## Suggested bounded engineering phases

**Phase A — Stabilize:** keep PR #34 and #32 under review; correct OpenAI 401 with full project-bound key; resolve S6 high dependency findings. No live secret reading in automation.

**Phase B — S2 identity:** OIDC discovery/JWKS, JWT validation of issuer/audience/algorithm/expiry, secure session lifecycle, tenant membership lookup, server enforced RBAC; negative security tests.

**Phase C — S3–S5 feature APIs:** tenant-scoped projects, real command and evidence lists, idempotency/audit, client state mapping, RTL/LTR, VoiceOver/TalkBack. No invented content or operational metrics.

**Phase D — Mobile RC:** linked EAS project, Apple signing, Android APK/iOS IPA, eight E2Es on both platforms, dependency audit closure, zero critical QA, 26 gate manifest.

**Phase E — SaaS production hardening:** threat model, TLS/WAF, OIDC/RBAC/RLS, observability, backups/restore, event replay, disaster recovery, capacity, multi-region only after proven and budget-approved.

## Exclusions

Architecture target is not the same as working code. Do **not** claim full active-active multiregion, Redlock, Kafka, OMEGA reasoning, self-healing, Stripe payments, or production governance on the basis of project requirements alone.
