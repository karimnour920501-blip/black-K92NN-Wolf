"""Offline tests for the one-request OpenAI connection probe."""
import io
import json
import os
import sys
import unittest
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import verify_openai as probe_module


class FakeResponse:
    def __init__(self, payload):
        self.data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return self.data


class VerifyOpenAITests(unittest.TestCase):
    def test_missing_key_does_not_make_network_call(self):
        def forbidden(*args, **kwargs):
            self.fail("network access attempted")
        self.assertEqual(probe_module.probe("", opener=forbidden), (False, "key_missing"))

    def test_exact_expected_reply_verifies_minimal_request(self):
        seen = {}
        def fake_open(request, timeout):
            seen["url"] = request.full_url
            seen["data"] = json.loads(request.data)
            seen["headers"] = dict(request.header_items())
            seen["timeout"] = timeout
            return FakeResponse({"output": [{"type": "message", "content": [
                {"type": "output_text", "text": "BLACKWOLF_OPENAI_OK"}]}]})

        ok, reason = probe_module.probe(
            "fake-only-secret", model="gpt-6-luna", project_id="proj_local_fake",
            opener=fake_open)
        self.assertEqual((ok, reason), (True, "verified"))
        self.assertEqual(seen["url"], "https://api.openai.com/v1/responses")
        self.assertEqual(seen["data"]["model"], "gpt-6-luna")
        self.assertEqual(seen["data"]["max_output_tokens"], 64)
        self.assertEqual(seen["data"]["reasoning"]["effort"], "none")
        self.assertFalse(seen["data"]["store"])
        self.assertEqual(seen["headers"]["Authorization"], "Bearer fake-only-secret")
        self.assertEqual(seen["headers"]["Openai-project"], "proj_local_fake")
        self.assertNotIn("fake-only-secret", json.dumps(seen["data"]))

    def test_http_error_returns_only_status_code(self):
        def fake_open(*args, **kwargs):
            raise HTTPError(
                probe_module.ENDPOINT, 403, "secret in error reason",
                {}, io.BytesIO(b"provider secret debug body"))
        self.assertEqual(probe_module.probe("fake-only-secret", opener=fake_open),
                         (False, "http_403"))

    def test_unexpected_generated_text_not_a_verified_connection(self):
        def fake_open(*args, **kwargs):
            return FakeResponse({"output": [{"content": [
                {"type": "output_text", "text": "something else"}]}]})
        self.assertEqual(probe_module.probe("fake", opener=fake_open),
                         (False, "unexpected_output"))

    def test_invalid_model_does_not_make_network_call(self):
        def forbidden(*args, **kwargs):
            self.fail("network access attempted")
        self.assertEqual(probe_module.probe("fake", model="", opener=forbidden),
                         (False, "invalid_model"))


if __name__ == "__main__":
    unittest.main()
