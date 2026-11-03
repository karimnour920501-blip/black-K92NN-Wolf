# BLACK-K92N-WOLF — Computer Use (isolated fixture integration)

**Status:** functional Python adapter, not a production remote-browser agent.
This component is additive; it does not modify existing Control Plane or Runtime endpoints.

## Architecture

- **Host**: `wolf_cua.runner` submits a Responses function tool `exec_py` and
  returns `function_call_output` with the matching `call_id`, including a fresh
  `input_image` (`detail: original`). `previous_response_id` retains model context.
- **Worker**: one persistent Python/Playwright process per run, with `browser`,
  `context`, `page`, and variables persisting between executions. Local fixture
  renders an offline badge form. The worker always adds a fresh screenshot.
- **Isolation**: `docker run --network none --read-only --cap-drop ALL
  --security-opt no-new-privileges:true --user 10001:10001` with no bind mounts,
  no Docker socket and no API key in the worker; limited CPU, memory, processes,
  and temporary filesystem. The host holds `OPENAI_API_KEY` only for live runs.
- **Consent**: Each model-produced script is shown to the operator and requires
  an exact `yes` at execution time. Declined scripts return a refusal to the model.
  Model output, page text and screenshots are **untrusted**. Guest image is removed
  after each run; no real accounts or network access.
- **Limits**: bounded API requests, code size, screenshot size, isolated process
  timeout and forced teardown. Verify actual DOM state after completion; a model
  completion message is not proof of success.

## Prerequisites

Docker Engine on an x86-64 or compatible host, Python 3.11+, OpenAI Python
SDK `3.31.0` for optional live runs, and access to `gpt-6-astra` with function
calling. API usage is billed if you use `--live`.

## Build and test

From this directory:

```bash
docker build -t wolf-cua-worker:local .
python -m unittest discover -s tests -v
python -m wolf_cua.cli --output evidence
```

The third command performs a **scripted offline rehearsal with no API key**:
fill `Mira`, click `Create badge`, inspect the live DOM, and save screenshot and
`result.json`. No model is involved in that command.

Optional live use, **after reviewing the billing and script-approval policy**:

```bash
python -m pip install -r requirements-host.txt
# Set OPENAI_API_KEY in your host environment using a secure secret manager.
python -m wolf_cua.cli --live --output evidence
```

The model's scripts run in the isolated container; the operator approves each
proposed script. Keep the demo offline. To work with real services, design a
separate, authenticated, policy-filtered egress gateway and stateful approval
workflow. Never expose this demo as an unauthenticated public HTTP endpoint.

### Host-only smoke test (not isolated)

If Docker is unavailable but Playwright and Chromium are installed on your
machine, you can test just the application logic with:

```bash
WOLF_CUA_CHROMIUM=/usr/bin/chromium python -m wolf_cua.cli --local-rehearsal --output evidence
```

**This is intentionally forbidden with `--live`.** A host-only rehearsal does
not establish isolation or production readiness.

## Evidence and gaps

- `python -m unittest discover -s tests -v` tests the Responses loop,
  `call_id` forwarding, approvals, image validation and failure cases.
- `python -m wolf_cua.cli` tests the real browser interaction, independently
  checks the DOM, and creates `evidence/badge-final.png` and `evidence/result.json`.
- Docker isolation and live API acceptance must be verified on the actual
  staging host. Browser scripts can perform arbitrary operations **inside the
  disposable worker**; code-execution namespaces are not security boundaries.
- No durable queue, identity federation, network policy for real destinations,
  automated security review, or cloud deployment is provided here.

Official references:
- https://developers.openai.com/api/docs/guides/tools-computer-use
- https://developers.openai.com/api/docs/guides/tools-computer-use-integration
- https://developers.openai.com/api/docs/guides/tools-computer-use-sdk-drivers
