# BLACK-K92N-WOLF Mobile MVP v1.0 — S6 E2E and release matrix

> Issue [#24](https://github.com/karimnour920501-blip/black-K92NN-Wolf/issues/24).
> Current status: **BLOCKED / NOT VERIFIED**. This is a test plan, NOT evidence that tests have run.

## Precondition

S1 branch `development/mobile-mvp-s1-evidence` contains an unauthenticated Expo demo shell.
S2-S5 authentication, tenant-aware backend integration and commands/evidence
must be implemented and reviewed BEFORE claiming S6 E2E completion.
Every case requires **both Android and iOS emulator/physical-device evidence**,
including app build IDs, OS/device, test account role, timestamp, test output,
screen recording/screenshot (redacted), and linked CI run.

| ID | Scenario | Expected acceptance | Required evidence |
| --- | --- | --- | --- |
| E2E-01 | Launch with no session; invalid login | No private data; invalid auth rejected; safe login/error state | Android + iOS logs/video and OIDC integration |
| E2E-02 | Expired/forged JWT and logout | 401; reauthentication; token/cache cleared; no token leaks in logs | Android + iOS screenshots and backend HTTP traces |
| E2E-03 | Tenant A → Tenant B switch | A's cached data invalidated; unauthorized tenant denied 403; no cross-tenant reads | Two tenants, two test users, server-side assertion and devices |
| E2E-04 | Viewer vs operator RBAC | Viewer cannot POST create/execute (403), operator allowed where implemented | Server integration response and app result on both platforms |
| E2E-05 | Commands and idempotency | Unsupported 409; supported command audited; double taps do not duplicate POST effects | Backend audit event, idempotency key, two device results |
| E2E-06 | Loading/empty/offline/429/5xx | Correct localized state; safe retries only; no infinite load, no stack trace | Network fault injection, screenshots, RTL and LTR |
| E2E-07 | Accessible bilingual navigation | 5 tabs, safe areas, Android TalkBack/iOS VoiceOver, font scaling, contrast and RTL/LTR | Accessibility audit and device videos |
| E2E-08 | Evidence & audit details | Authentic `verified` only after server validation; failed/unavailable never green; 403 handled | Backend hash-chain proof scope + iOS/Android recording |

## Security release checks

- **JWT:** issuer, audience, signature, expiry, algorithm allowlist and nonce/state where applicable; reject forged/expired tokens.
- **RBAC:** enforce roles on the backend, not only hide UI buttons; verify viewer/operator matrices and 403.
- **Tenancy:** enforce authorized tenant in data access (RLS or equivalent); prove A/B isolation and cache partition/clear.
- **No secret logs:** no Authorization bearer, access/refresh token or PII in error/analytics/build logs; redaction test.
- **Critical defects:** documented `open_critical = 0` with linked bug dashboard and QA sign-off.
- **Dependency scan:** actual `npm audit --omit=dev --audit-level=high` report, or signed exception with risk owner. No automatic waiver.
- **Lint:** add and pass a genuine ESLint setup for the application; current S1 has no `lint` script. TypeScript is NOT a replacement for lint.
- **Accessibility:** device-level VoiceOver/TalkBack + text scaling and contrast; S1 static contrast tests are only partial evidence.

## Evidence contract

Records in `mobile/s6/release-evidence.json` start **pending**.
For a case to become `passed`, a reviewer must link a real trusted
GitHub Actions/issue or Expo build URL. For E2E-01..08 provide at least two
links and declare both platforms. `candidate_commit` must be an actual
40-digit commit SHA for the tested release candidate. Never supply fake links,
synthetic screenshots, placeholder builds, or manually relabel tests as passing.

Run locally:

```bash
node --test scripts/tests/s6-release-gate.test.mjs
node scripts/s6-release-gate.mjs mobile/s6/release-evidence.json
```

The second command MUST return nonzero while any gate is pending. The validator
checks evidence-record format, not external artifact authenticity; human QA,
security approval, code review, and explicitly authorized merge are still required.

## Current release blockers (initial inspection, 2026-11-01)

- Source branch has S1 demo UI only: no real login, JWT-backed session, tenant switching, protected commands or evidence APIs.
- EAS project ID is missing in `expo.extra.eas.projectId`; no proven Android APK or signed iOS IPA.
- iOS signing/Apple Developer membership and Expo cloud permissions have not been independently verified.
- No real device/emulator execution of E2E-01..08 or documented manual QA for S6.
- Lint, complete accessibility testing and dependency scan require actual linked runs.
- Current successful S1 CI proves npm test/typecheck/Metro export only, not native builds:
  https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/40996051123

**No staging/prod release, no `main` merge and no Production claim until S6 evidence gate plus authorized human approval.**
