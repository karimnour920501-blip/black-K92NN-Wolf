from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
import src.app as module

client = TestClient(module.app)

def test_real_sdk_import():
    import openai
    assert hasattr(openai, "AsyncOpenAI")

def test_health():
    assert client.get("/health").json() == {"status": "ok"}

def test_empty_prompt_rejected():
    assert client.post("/api/v1/respond", json={"prompt": ""}).status_code == 422

def test_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert client.post("/api/v1/respond", json={"prompt": "hello"}).status_code == 503

def test_success_with_mock_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(output_text="mock answer")))
    monkeypatch.setattr(module, "AsyncOpenAI", FakeClient)
    response = client.post("/api/v1/respond", json={"prompt": "hello"})
    assert response.status_code == 200
    assert response.json() == {"text": "mock answer"}

def test_upstream_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(create=AsyncMock(side_effect=module.OpenAIError("simulated")))
    monkeypatch.setattr(module, "AsyncOpenAI", FakeClient)
    assert client.post("/api/v1/respond", json={"prompt": "hello"}).status_code == 502
