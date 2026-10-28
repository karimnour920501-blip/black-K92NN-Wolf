# BLACK-K92N-WOLF — Clean Foundation

A small independently testable Python foundation. It is deliberately isolated from the legacy repository code.

## Test

```bash
cd foundation
PYTHONPATH=src python -m unittest discover -s tests -v
```

The foundation provides deterministic JSON serialization and SHA-256 digests only. It is **not** a production event store, payments system, authentication service, or distributed replay engine.

## Future projects

Add each future application in its own directory or repository with a clear README, tests, and CI. Do not copy legacy services without auditing their dependencies and secrets.
