# BLACK-K92N.WOLF — Source Recovery Staging

Status: RECOVERY_IN_PROGRESS / NOT_PRODUCTION_READY

This branch is isolated from main. No deployment or merge is authorized.

## Verified source archive inventory
- BLACK-K92N-WOLF-Recovery-Runtime-v0.2.1.zip
  - components/control-plane/control_plane/core.py
  - components/control-plane/control_plane/server.py
  - components/control-plane/tests/test_core.py
  - components/control-plane/tests/test_control_plane.py
  - components/runtime/runtime.py
  - components/runtime/tests/test_runtime.py
- BLACK-K92N-WOLF-Control-Plane-Unified-v0.2.0.zip (comparison baseline)
- BLACK-K92N-WOLF-Control-Plane-MVP-v0.1.0-verified.zip (legacy security baseline)
- BLACK-K92N-WOLF-Control-Plane-MVP-v0.1.0.zip (legacy comparison)

## Restore policy
1. Preserve original source bytes and relative paths.
2. Record SHA-256 for each restored source and source archive.
3. Do not conflate Control Plane with Runtime: they remain separate components.
4. Uer.Api and Uer.Api.StoreContracts are NOT recovered in this branch.
5. Require isolated tests, API authorization checks, audit-chain checks, and integration tests before merge.
6. No production release, deployment, or main-branch merge.

## Evidence boundary
The source archive inventory was inspected locally. This staging README does not claim source files were committed or tests were executed in GitHub Actions.
