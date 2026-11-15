# BLACK-K92N-WOLF OpenAI Developers Lab

Isolated Python/FastAPI proof of concept. Not production-ready.

## Local run
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn src.app:app --reload
```

Configure OPENAI_API_KEY in your shell for real requests. Never commit keys.

## CI
GitHub Actions installs the real OpenAI Python SDK and runs offline unit tests.
The manually triggered live-smoke job uses an OPENAI_API_KEY secret from the
`openai-live-test` GitHub Environment; configure approval protection and
a restricted, low-budget project key before using it. The live test costs API
tokens and requires network access and billing access. No live test is run
on push or pull requests.
