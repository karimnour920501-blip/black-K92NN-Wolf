# BLACKWOLF K92N Hosting 1.0.1 — Deployment Hardening

Baseline: merged PR #37, commit `8b2e42672925163db98a4d2ee2de7eb2107018b3`.
Hosting version only; accounting schema, C# core, hash contract and HTTP API are unchanged.

## P0.1 Recovery acceptance

`python3 tools/recovery_ci.py` starts the real compiled ASP.NET host with synthetic USD/TRY entries, two customers, a reversal, a period lock and a governance event. It captures a separate expected anchor before backup. It backs up a live database through SQLite's backup API, transports only the DB file to an independent temporary directory and restores to a NEW path after removing the original source directory. It verifies:

- Exact table rows (including journal headers/lines/seals and SQLite sequences), four entries, nonzero balances by customer/currency, and HeadHash.
- `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, `/api/integrity?expectedHead=...` and deterministic governance replay.
- Restored idempotency, wrong-anchor rejection and no extra entries from a retry.
- Corrupt-header input, FK-broken input, changed transport checksum, WAL-dependent input, overwrite attempts and source-as-destination fail without changing the original records, balances or HeadHash.

`tools/docker_smoke.py` additionally exports the actual backup outside the source container using `docker cp`, restores it on the CI host, imports the NEW restored file into a separate disposable volume and verifies it through a newly started non-root container. No original data volume is mounted into that restored app. It compares count, nonzero balance, HeadHash and both SQLite PRAGMAs. The root preparation container owns only disposable CI paths; it is not a workaround or evidence for Render mount ownership.

`backup.py backup` supports live WAL databases and performs structural and FK validation in one read snapshot. `restore-new` accepts only a standalone backup, freezes input bytes before SQLite reads them, and can require an externally recorded SHA-256. It never replaces an existing path. The tool does not authenticate the backup author or certify accounting semantics: keep anchors/checksums outside the backup and verify the restored API before any live promotion. A checksum shipped by an attacker with their modified backup is not a trusted anchor.

Example (operator paths must be selected explicitly):

```bash
python3 tools/backup.py backup /live/k92n-local.db /independent/backup.db
python3 tools/backup.py restore-new /independent/backup.db /quarantine/k92n-local.db --expected-sha256 EXTERNALLY_RECORDED_SHA256
```

Do not restore by overwriting an active SQLite file. Do not copy just the main file from a live WAL database. This revision adds no automated production promotion and no schema migration.

## P0.2 Supply chain acceptance

- `infra/supply-chain-lock.json` records the official action release tags and resolved commit SHAs plus MCR manifest URLs, digests, and resolution time.
- Both Docker bases use verified SHA-256 manifest digests; all three actions in the K92N workflow use full commit SHAs. Credentials are not persisted by checkout; workflow permissions remain contents:read.
- All module restores are locked, with `NuGet.Config` restricted to nuget.org. CI uses a fresh per-run package directory and no package cache restore.
- `tools/verify_supply_chain.py` verifies the pin policy; checks each restored package against lock contentHash and cached archive SHA-512; invokes `dotnet nuget verify --all` for repository/package signatures. NuGet's normalized lock contentHash is intentionally different from raw SHA-512 of a repository-signed archive.
- A real NuGet advisory query includes transitive packages. Missing project data, warnings/errors, or reported vulnerabilities fail the gate. This is not an OS/runtime vulnerability scan.
- CI records the derived image ID and OS package inventory. APT repositories and hosted runner images remain updateable, so this is NOT a bit-for-bit reproducible build or a claim that all OS dependencies are immutable. Both are explicitly outside the pin gate's limited scope.

Updating pins requires checking the release in its official action repository, resolving an annotated tag to its commit if needed, hashing the exact MCR manifest response against Docker-Content-Digest, editing both the lock and its consumers in a new PR, and rerunning all gates. Digest pinning also freezes security updates until a reviewed update; review pins and advisories regularly.

## Evidence and remaining gates

New results are uploaded per commit in `k92n-verification-<commit>`: recovery-ci-results.json, docker-ci-results.json, dependency-integrity-results.json, supply-chain-results.json, nuget-audit-ci.json, nuget-audit-gate.json, container-image-id.txt, container-packages.tsv, http-results.json. A workflow's existence is not a PASS. Read the run conclusion, per-step exit status and artifact content.

Local execution before opening the PR: Recovery 34 checks PASS; Python 55 tests PASS; locked Release build PASS; NuGet package signatures/integrity PASS; advisory query reported no known affected packages. Actual Docker checks for this revision require GitHub CI because this local executor has no Docker daemon. These observations must not be substituted for the new CI result.

P0.3 Render Pilot = NOT_RUN. No paid subscription, Render resource, restart or redeploy is authorized by this hardening revision.
P0.4 physical iPhone Safari pilot = NOT_RUN.
P1 multi-tenant identities/RBAC/isolation = DEFERRED.
PRODUCTION_READY = FALSE.

Reference semantics:
https://sqlite.org/pragma.html
https://docs.github.com/en/actions/reference/security/secure-use
https://learn.microsoft.com/en-us/nuget/consume-packages/package-references-in-project-files
