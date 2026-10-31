# BLACK-K92N-WOLF

Source repository for several **separate, evidence-gated** BLACK-K92N-WOLF components. This is not a single, verified production deployment.

## Source inventory

| Path | Current scope |
| --- | --- |
| [components/control-plane](components/control-plane) | Python read-only project/control API with a local SQLite store, policies, audit chain and tests. Connector configuration remains disabled by design. |
| [components/runtime](components/runtime) | Local static-site deploy/preview runtime and tests. This is **not** cloud hosting. |
| [source/blackwolf-uer-v0.1.1-reliability](source/blackwolf-uer-v0.1.1-reliability) | .NET UER reliability source and store-contract test project. |
| [recovery](recovery) | Source recovery notes, manifests and evidence; preserve until reviewed. |
| [apps/blackwolf-ai](apps/blackwolf-ai) | Isolated local chat preview backed by OpenAI Responses API. Does not modify the other components. |
| [.github/workflows](.github/workflows) | Component-specific test workflows, not deployment approval. |

## BLACKWOLF AI chat preview

Read [apps/blackwolf-ai/README.md](apps/blackwolf-ai/README.md) for local setup and security boundaries. The OpenAI secret must stay server-side; no key or account is linked automatically by merging code.

## Evidence policy

- Keep original source and recovery evidence until an explicit review establishes redundancy.
- Test and review new code on a development branch and PR before merging to main.
- GitHub Actions, local tests, live provider connectivity, staging deployment and production readiness are **different gates**. Never label a feature live without matching evidence.
- No automatic write operations, deployments, account integrations or production approval are implied by this repository.
