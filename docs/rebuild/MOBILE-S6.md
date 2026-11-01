# Mobile MVP v1.0 — reconstruction through S6

**Issue #24 / PR #32:** S6 is an evidence/release-candidate gate built on the S1 source branch; the app is not a finished integrated authenticated mobile product.

## Actual implementation by sprint

| Sprint | Expected function | Recovered source and status | Missing proof |
| --- | --- | --- | --- |
| S1 | Expo Router TS, tokens, 5 tabs, states, safe-area | Code on `development/mobile-mvp-s1-evidence`; source CI PASS | bilingual/device A11y QA incomplete |
| S2 | OIDC login, secure JWT/session, selected tenant | Requirements in Issues #13-14; **not implemented end to end** | issuer/audience/signature/expiry, real provider, secure storage and tenant A/B |
| S3 | Dashboard/projects, viewer/operator, tenant-scoped API | Requirements in Issues #15-17; **not implemented in mobile S1 shell** | live API contracts, GET/POST, forbidden/offline tests |
| S4 | 100 commands catalog, details, design-brief invocation | Requirements in Issues #18-20; **demo UI only** | real canonical dataset, idempotent command backend, RBAC |
| S5 | evidence/audit verification, settings, logout, RTL/LTR | Requirements in Issues #21-23; **not implemented** | real hash verification/403, storage purge, localization, QA |
| S6 | Android/iOS native builds, E2E-01..08, security, A11y, QA, release gate | release manifest + E2E matrix + guarded EAS/CI source in draft PR #32 | EAS native builds, device tests, 0 critical QA, security scan closure |

## Verified code quality

- Successful S1 CI: https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/40996051123 (npm lock install, source tests, TS, Metro export — **not APK/IPA**).
- S6 source pipeline after lint fix: https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41260312382 . 17/17 source tests; 12 TS/TSX files source AST lint clean; TS typecheck/Metro PASS; overall run FAIL due dependency audit.
- 7/7 S6 evidence policy tests verify that a pending gate or missing Android/iOS evidence blocks release. Synthetic test fixtures do **not** prove any real E2E test completed.
- Latest S6 CI with JSON audit artifact: https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41260474783 — `mobile-s6-audit-41260474783` artifact; job still fails on high advisories.

## Security findings

- `npm audit --omit=dev --audit-level=high` found **31 advisories (5 high, 25 moderate, 1 low)** on installed Expo dependency graph. The count is scanner findings, not confirmation that five vulnerabilities are reachable from the deployed application.
- Existing `mobile/s6/S6-DEPENDENCY-TRIAGE.md` documents `decode-uri-component`, `image-size`, `deepmerge`, including dependency chains and why `npm audit fix --force` should NOT be used blindly.
- Lint implementation is currently a narrower TypeScript AST policy; **not** the full Expo ESLint ruleset. No fake claim of passing comprehensive ESLint.
- `mobile/s6/release-evidence.json` has **26 pending gates**. Genuine release evidence must include the tested candidate commit, each gate result and source links reviewed by humans.

## Native build preconditions

- EAS profile `s6_preview` declares an internal Android APK and signed iOS ad-hoc build. There is **no independently verified EAS project UUID** in `expo.extra.eas.projectId`, Apple signing, registered iPhone UDID or `EXPO_TOKEN` readiness.
- The `mobile-s6-eas-builds.yml` workflow is **manual only**, protected by confirmation and secret prerequisites. It has not produced an Android or iOS artifact.
- User uses iPhone; Expo cloud may avoid a personal computer, but Expo project linkage, Apple developer membership, iOS signing and actual device QA are still mandatory.

## E2E acceptance cases

1. **E2E-01** — no session/invalid credentials fail closed.
2. **E2E-02** — expired/forged JWT 401 and logout clears local sensitive state.
3. **E2E-03** — switching tenant A/B invalidates A cache and rejects unauthorized tenant.
4. **E2E-04** — viewer 403 on create/execute; operator allowed only by backend.
5. **E2E-05** — command idempotency and unsupported 409, audit provenance.
6. **E2E-06** — Loading/Empty/Offline/429/5xx safe error and retry semantics.
7. **E2E-07** — accessible bilingual tab navigation, RTL/LTR, VoiceOver/TalkBack and text scaling.
8. **E2E-08** — real evidence verified only after authentic backend result; forbidden/failed states cannot be shown as valid.

Every case requires **both Android and iOS emulator/physical-device recordings/logs and backend contract evidence**. This matrix is an acceptance plan, not executed tests.

## Next implementation order

1. Security dependency triage and Expo-supported upgrades with CI source/Metro + native checks.
2. S2 identity provider + server-validated OIDC/JWT session and tenant context, no client role authority.
3. S3 read-only tenant-scoped dashboard/projects then write commands behind RBAC and idempotency.
4. S4/S5 genuine command catalog and evidence/audit APIs, logout and bilingual accessibility.
5. Explicitly authorized EAS Android/iOS builds, device QA, E2E-01..08, release manifest and code review.
6. Only after all 26 gates pass plus human security/release approval may v1.0 be designated Release Candidate. Production requires its own independent gate.

## No-go conditions

Never ship because static mock or source test passes, never place OpenAI API key in Expo JS, never fabricate `Verified` audit state, never merge to `main` without owner approval. Keep this separate from independently deployed OpenAI web prototype.