"""Offline tests for the one-request OpenAI connection probe."""
import io
import contextlib
import json
import os
import sys
import unittest
from unittest import mock
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

    def test_local_preflight_accepts_only_credible_key_shape(self):
        valid = "sk-test-only-local-mocked-key-12345"
        self.assertIsNone(probe_module.check_configuration(
            valid, "gpt-6-luna", "proj_dvKpPmjuD9RUvEe2mYN4noiZ"))
        for key in (
            "", "key_tracking_identifier", "user_account_identifier",
            "proj_dvKpPmjuD9RUvEe2mYN4noiZ",
            "sk-...IGYA", "sk-too-short", " sk-test-only-local-mocked-key-12345",
            "sk-test-only-local-mocked-key-12345\n",
        ):
            with self.subTest(key=key):
                self.assertIsNotNone(probe_module.check_configuration(
                    key, "gpt-6-luna", "proj_dvKpPmjuD9RUvEe2mYN4noiZ"))

    def test_project_id_and_model_rejected_before_network(self):
        key = "sk-test-only-local-mocked-key-12345"
        self.assertEqual(probe_module.check_configuration(
            key, "gpt-6-luna", "user_instead_of_project"),
            "invalid_project_id")
        self.assertEqual(probe_module.check_configuration(
            key, "gpt-6-luna\n", "proj_test123"), "invalid_model")

    def test_preflight_never_invokes_paid_api(self):
        env = {
            "OPENAI_API_KEY": "sk-test-only-local-mocked-key-12345",
            "OPENAI_PROJECT_ID": "proj_dvKpPmjuD9RUvEe2mYN4noiZ",
            "OPENAI_MODEL": "gpt-6-luna",
        }
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(probe_module, "probe",
                                  side_effect=AssertionError("network attempted")), \
                contextlib.redirect_stdout(out):
            result = probe_module.main(["--preflight"])
        self.assertEqual(result, 0)
        self.assertIn("authenticity NOT VERIFIED", out.getvalue())
        self.assertNotIn(env["OPENAI_API_KEY"], out.getvalue())

    def test_main_sanitizes_http_401_and_reports_recovery(self):
        env = {
            "OPENAI_API_KEY": "sk-test-only-local-mocked-key-12345",
            "OPENAI_PROJECT_ID": "proj_dvKpPmjuD9RUvEe2mYN4noiZ",
            "OPENAI_MODEL": "gpt-6-luna",
        }
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(probe_module, "probe", return_value=(False, "http_401")) as called, \
                contextlib.redirect_stdout(out):
            result = probe_module.main([])
        self.assertEqual(result, 1)
        called.assert_called_once_with(
            env["OPENAI_API_KEY"], model="gpt-6-luna",
            project_id="proj_dvKpPmjuD9RUvEe2mYN4noiZ")
        self.assertIn("http_401", out.getvalue())
        self.assertNotIn(env["OPENAI_API_KEY"], out.getvalue())

    def test_main_refuses_masked_secret_without_paid_call(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-...IGYA",
            "OPENAI_MODEL": "gpt-6-luna",
        }, clear=True), mock.patch.object(
                probe_module, "probe", side_effect=AssertionError("network attempted")), \
                contextlib.redirect_stdout(out):
            result = probe_module.main([])
        self.assertEqual(result, 2)
        self.assertIn("invalid_api_key_format", out.getvalue())
        self.assertNotIn("sk-...IGYA", out.getvalue())

    def test_http_401_does_not_include_provider_error_body(self):
        def fake_open(*args, **kwargs):
            raise HTTPError(
                probe_module.ENDPOINT, 401, "token leaked in reason",
                {}, io.BytesIO(b"provider could expose secret details"))
        self.assertEqual(probe_module.probe(
            "fake-only-secret", opener=fake_open), (False, "http_401"))



if __name__ == "__main__":
    unittest.main()
