# Mobile S6 — Dependency security remediation register

Status: **OPEN — release blocked**. This document records observed automated audit findings and target mitigations; it does NOT certify exploitability or a clean dependency tree.

## 2026-11-25 rerun and non-force probe

- [S6 CI rerun, attempt 3](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41260478561): production dependency audit reported **5 high, 13 moderate, 0 low, 0 critical** and failed. Artifact ID `15020445924`, SHA-256 `63cf7553fc133a69193123acca4a3ba08fa7d9bb5713e806c26e24d1452c94bb`.
- Current high-severity package entries: `decode-uri-component`, `expo-router`, `image-size`, `postcss`, and `query-string`. Counts are npm audit metadata, not a count of independently confirmed exploits.
- [Non-force isolated probe](https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/45612782812) used `npm audit fix --package-lock-only --ignore-scripts`, without `--force`. Candidate source tests, typecheck, limited lint and Metro export passed, but the audit still had **5 high and 12 moderate**; the security gate failed.
- The candidate lockfile changed about 9,953 diff lines and remains in the CI artifact only. It has not been committed or approved. Audit suggested major-version fixes for some paths; assess Expo-compatible upgrades incrementally and verify devices, rather than forcing a major change. See [Expo SDK upgrade guidance](https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/).
- Native Android/iOS builds and mobile E2E remain unverified; S6 release remains blocked.

## Historical observation — 2026-11-01
- S6 CI run: https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/41259757621
- `npm audit --omit=dev --audit-level=high` on the locked Expo SDK 54 project: **31 advisories: 5 high, 25 moderate, 1 low**. Audit job failed.
- `npm audit fix --force` offers breaking changes across Expo and expo-router. **Do not run it without a dedicated Expo migration/test review**.

## High-risk dependency chains to triage

| Package/advisory | What audit reported | Plan | Evidence needed |
| --- | --- | --- | --- |
| `decode-uri-component` — GHSA-qr28-fpjm-wq7f | High availability/DoS via query-string / Expo Router dependency | Investigate an Expo-router-compatible resolver upgrade or safe override to `decode-uri-component@0.5.1` (patched according to GitHub advisory), regenerate lock in CI and verify application routing | Fresh npm audit + Expo navigation E2E on iOS/Android |
| `image-size` — GHSA-5p2g-fcmc-qvqq | High image parser DoS in versions through 2.0.2 | GitHub advisory reports **no patched version**; do NOT invent `2.0.3` or force an unpublished package. Analyze reachability (build-time dev path vs runtime), restrict untrusted uploads and seek upstream fix or narrowly scoped verified mitigation | Dependency paths, proof of reachability, upstream remediation and owner-approved risk treatment |
| `image-size` — GHSA-w3rx-r6r6-pgpr | High ICNS parser DoS | Same owner-reviewed upstream/patch and reachability approach; no global audit bypass | Fresh audit and evidence of affected parser avoidance or patch |
| `deepmerge` — GHSA-gcqx-w48m-w2h4 | Potential prototype poisoning in transitive Expo toolchain | Investigate versions and actual call path; apply compatible upstream package update after package-lock regeneration and Metro/native smoke | Audit report, lockfile diff and build compatibility |

GitHub advisories: https://github.com/advisories/GHSA-qr28-fpjm-wq7f ; https://github.com/advisories/GHSA-5p2g-fcmc-qvqq ; https://github.com/advisories/GHSA-w3rx-r6r6-pgpr ; https://github.com/advisories/GHSA-gcqx-w48m-w2h4

## Upgrade work requirements
1. Create a dedicated dependency-remediation branch and regenerate `package-lock.json` with the same npm major used in CI.
2. Prefer Expo-compatible upgrades. Try non-force repairs in a sandbox; never merge an auto-generated major upgrade without review.
3. Reproduce `npm ci`, `npm test`, `npm run typecheck`, `npm run lint`, Expo Metro export and 8 dual-platform E2E tests after changes.
4. Re-run `npm audit --omit=dev --audit-level=high`. If an advisory has no published fix, escalate to owner with evidence-based reachability assessment; never silently suppress it.
5. Preserve full scan logs, affected versions, PR review and risk-owner signoff. Leave `dependency_scan` S6 gate pending until accepted policy and real evidence are provided.

**Security decision:** 5 high findings mean S6 cannot be called release-ready; they are scan findings, not proof of an exploit in the mobile application.
