# iPhone-only QA / EAS readiness — 2026-10-30

## Evidence boundary
GitHub Actions Mobile S1 Evidence Gate #35 succeeded: source completeness, npm ci, Node tests, TypeScript and Expo Metro export. This is NOT an iOS IPA build or physical device QA.

## Prerequisites
1. Expo account with access to the project, and an EAS project ID linked to this repository's app config.
2. Active paid Apple Developer Program membership and valid iOS signing credentials in EAS.
3. Physical iPhone UDID registered with the correct Apple team and included in the ad hoc provisioning profile.
4. GitHub Actions repository secret `EXPO_TOKEN` (enter only in GitHub Secrets, never in code, issues, chat, or logs).
5. Explicit approval before starting a potentially billable cloud build.

## Phone-only setup
- On iPhone Safari sign in at https://expo.dev and create/link the Expo project. Copy the exact EAS project UUID into `app.json` under `expo.extra.eas.projectId` on the isolated development branch; do not invent a UUID.
- On iPhone Safari sign in to https://developer.apple.com/account and ensure Apple Developer Program is active. Initial EAS signing setup may require an interactive EAS CLI session in a cloud development environment; the manual CI workflow intentionally cannot perform this enrollment.
- Use EAS device registration link/profile for the iPhone, approve the enrollment and refresh ad hoc provisioning. A registered device must be included in the profile used to sign the IPA.
- On iPhone Safari open the repository Settings > Secrets and variables > Actions and create secret `EXPO_TOKEN`, using a token created in Expo account settings. Never post the token.
- After EAS project and signing are ready, open GitHub Actions > Mobile S1 iPhone EAS Preview (manual), select the evidence branch, and enter READY. This triggers `eas build --platform ios --profile ios_preview --non-interactive --wait`.
- When successful, open the build's install link on the registered iPhone and test navigation, safe areas, system states, touch targets, RTL/LTR, and accessibility. Record actual screenshots, device/iOS version, failures and build ID in Issue #10.

## Important limitations
- This workflow will fail fast if `EXPO_TOKEN` or `expo.extra.eas.projectId` is absent. It does not configure Apple signing automatically.
- No Expo/Apple credentials have been provisioned by this commit; no iOS build has been triggered or installed.
- `ios_simulator` is for simulator testing only and is not an installable iPhone build.
- The app is an unauthenticated demo shell. Session restore and complete bilingual QA are not implemented/verified.
- No main merge or production claim.
