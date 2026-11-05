# BLACK-K92N-WOLF — Unified Execution Contract v1.0
Status: ARCHITECTURE_SPECIFIED; only the existing C# API and its CI-tested operations are implemented.
Budget: $0 cloud hosting; GitHub-hosted standard runner on public repository; no deployment.

## Source of truth and scope
- C# ASP.NET Core 8 (`csharp/BlackWolf.Api`) is the only verified executable application in this integration scope.
- PostgreSQL 16 stores projects, server metadata, and audit records. No SSH execution.
- Python agents, Kafka, Redis, pgvector, HLC, replay, Ed25519, RLS, federated learning, billing, AWS active-active, and Azure deployment are NOT_IMPLEMENTED unless separately proven.
- No secrets, real user data, billing, or external API calls in CI.
- Do not conflate conceptual historical Wolf-KN92 v7 code with the current GitHub source.

## Target modules and dependency order
1. Identity & tenancy: authenticated principals, tenant_id on all records, PostgreSQL RLS, negative cross-tenant tests.
2. Event ledger: transactional append-only events, scoped idempotency keys, canonical payload serialization, monotonic tenant stream sequence, SHA-256 previous-hash chain, transactional outbox.
3. Replay: pure versioned reducers, deterministic ordering, canonical state hash, migration/version contract; model inference results are recorded as inputs rather than rerun nondeterministically.
4. Integrity: independent verifier, Ed25519 signing keys in a managed secret store, rotation, seal capsules and tamper tests.
5. Governance: explicit policy versioning, deny-by-default, PR-02/03/04/05/06 handlers and deterministic fixtures.
6. AI runtime: separate worker interface; optional Python service, model/version metadata, budget and permission gates.
7. External adapters: Meta, Shopify, Stripe, OpenAI behind disabled-by-default ports and contract tests.
8. Infrastructure: observability, rollback, backups, disaster recovery, regional topology only after evidence.

## Critical design constraints
- A hash chain detects modification only with a trusted checkpoint or signature anchored outside mutable storage; database rows alone are not immutable.
- Replay determinism applies to recorded inputs and versioned pure reducers; LLM outputs, wall clocks, randomness and external side effects must be captured as events.
- HLC alone does not guarantee total cross-region ordering; define a stream authority or conflict-resolution policy.
- Active-active multi-writer PostgreSQL and CRDT merge require separate consistency semantics, not a checkbox.
- Offline operation is a client capability, not proven by a server-side Compose test.
- Emergency stop must revoke actual execution permission and be tested; a UI alert is not a kill switch.
- Avoid emotional or behavioral profiling without consent, transparency, retention limits and deletion mechanisms.

## Evidence promotion gate
SPECIFIED -> SOURCE_AVAILABLE -> BUILD_PASS -> INTEGRATION_PASS -> SECURITY_PASS -> PRODUCTION_VERIFIED.
Evidence must include commit SHA, workflow run URL, test command, test output, and environment. Missing proof means NOT_VERIFIED.
Current state: C# CI success; broader platform NOT_IMPLEMENTED / NOT_VERIFIED.
