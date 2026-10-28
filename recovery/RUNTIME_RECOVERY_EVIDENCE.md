# BLACK-K92N.WOLF — Runtime original recovery evidence

Date: 2026-10-22
Branch: recovery/runtime-original-2026-10-22
Source archive: BLACK-K92N-WOLF-Recovery-Runtime-v0.2.1.zip
Source archive SHA-256: e4f52c1dfbe55edf1ca0c721c0fb8b034a00d3dc29b9254db26173f4350f60bd

## Recovered original source
- components/runtime/runtime.py — SHA-256 3284ad9be08243c5f142d7afcb7cc4e03b29f15a040014588d8e26cfe9050368
- components/runtime/tests/test_runtime.py — SHA-256 8b4e522de4219734ee5f33c6671ea671ce1a1c0c3eadd339004d982302f1ed92
- components/runtime/README.md — SHA-256 79ea1f0aa047f245d239354eccce7ab1a2913a7a414689e77a4da437e57e5983
- components/runtime/projects/example-site/index.html — SHA-256 53e374ed30b1672fb716194897abbd8474121f3473133fca227edbd9f1a4d63c

All four GitHub file contents were independently fetched and matched against source archive file text.

## Tests
- Local Python 3.13, `python -m unittest discover -s tests -v`: 5/5 PASS
- ResourceWarning: unclosed sqlite3 connections observed and not fixed in this byte-for-byte recovery.
- GitHub Actions workflow: .github/workflows/recovery-runtime.yml
- GitHub Actions result: NOT_VERIFIED until a concrete run ID and run logs can be inspected.
- Integrated tests with Control Plane: NOT_RUN.
- Distributed deployment/production: NOT_VERIFIED.

## UER gap
The Uer.Api P1 integration-candidate README describes a source tree and 9 C# StoreContracts, but the original complete source archive is not among the verified accessible archives. Drive searches for UER, StoreContracts, blackwolf-uer yielded no exact source archive. Referenced project paths are absent on main:
- source/blackwolf-uer-v0.1.1-reliability/src/Uer.Api/Uer.Api.csproj
- tests/Uer.Api.StoreContracts/Uer.Api.StoreContracts.csproj

No UER substitute source was fabricated; .NET/Docker gates remain blocked and release is prohibited.

## Branch safety
This is an isolated recovery branch. Do not merge into main or deploy without explicit authorization and passing release gates. Earlier PR #1 was already merged into main at c9073b16199b3d28fe210503324ff5e9fef4cdf0, and this recovery does not reverse that historical event.
