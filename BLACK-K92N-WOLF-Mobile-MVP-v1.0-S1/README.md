# BLACK-K92N-WOLF Mobile MVP v1.0 — Sprint S1

**Status: S1 source scaffold, not a production app.** React Native / Expo Router / TypeScript.

## Included
- Design tokens in `src/design/tokens.json` (dark imperial palette, spacing, type scale, touch target).
- Expo Router splash and five-tab navigation: Home, Projects, Commands, Evidence, Settings.
- Shared accessible `Screen`, `InfoCard`, `StatePanel` components.
- Pure HTTP error-state mapping; automatic retry allowed for safe GET/HEAD server errors only.
- Dependency-free Node tests for tokens, route presence, state handling and contrast.

## Run (when npm registry is reachable)
```bash
npm install
npm run typecheck
npm test
npm start
```
Use Expo Go or a development build matching the installed Expo SDK. Android/iOS native build was **not** executed in this environment.

## Security / functionality boundary
- **No authentication implemented.** Splash explicitly offers only an unauthenticated **demo shell**. No private data fetched or persisted.
- **No backend API wired.** Counts and labels are explicitly static metadata, not operational metrics.
- Commands, projects, evidence and settings are placeholder screens for later sprints; only navigation and state components are part of S1.
- No fake session, JWT, audit verification, or production readiness claims.
- Arabic UI is initial RTL-aware content, but comprehensive locale switching and bidirectional QA belong to later sprints.

## Acceptance
`npm test` validates static invariants. `npm run typecheck` and Expo device testing require `npm install`; CI and device validation remain pending.
