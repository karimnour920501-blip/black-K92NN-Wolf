# Legacy repository inventory — 2026-10-28

Source: `karimnour920501-blip/black-K92NN-Wolf`, branch `main`
Verified Git tree SHA: `aa0978fdb70e63a6390b26b0d9146400e08f0af3`
Git tree: 61 entries (directories and files); API response `truncated=false`.

## Confirmed code areas

- `components/control-plane/`: Python server, core, unit tests.
- `components/runtime/`: Python runtime, tests and example site.
- `source/blackwolf-uer-v0.1.1-reliability/`: C# API, examples, scripts and documentation.
- `tests/Uer.Api.StoreContracts/`: C# test project.
- `recovery/`: recovery notes and source manifest.
- `.github/workflows/`: recovery and source-build CI.
- `scripts/emit-gates.js`: JavaScript script.

## Strict status

This is a source-tree inventory, **not** a backup or quality certification. No mirror clone, branch/tag history export, issue export, release export, artifact export, or restore test has been completed. No old repository was deleted.

## Mandatory gates before deletion

1. Export complete Git mirror to storage independent of this repository.
2. Verify mirror refs, branch/tag coverage and restoration.
3. Export relevant GitHub metadata (issues, PRs, releases, Actions artifacts) separately.
4. Review secrets, licensing, dependencies and functional test evidence.
5. Create a new public repository and migrate reviewed code.
6. Run CI in the destination and check integrations.
7. Obtain separate explicit confirmation before deleting the old repository.

**Do not delete the original repository until every gate is evidenced.**
