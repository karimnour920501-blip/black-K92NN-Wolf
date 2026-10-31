import io
import json
import os
import socket
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import server as app


class ValidationTests(unittest.TestCase):
    def test_valid_history(self):
        self.assertEqual(app.validate_input({'message': 'hello', 'history': [
            {'role': 'assistant', 'content': 'Hi'}]}),
            [{'role': 'assistant', 'content': 'Hi'}, {'role': 'user', 'content': 'hello'}])

    def test_replay_accepts_same_long_message_as_initial_input(self):
        long_message = 'ع' * 8_000
        self.assertEqual(
            app.validate_input({'message': 'follow-up', 'history': [
                {'role': 'user', 'content': long_message},
                {'role': 'assistant', 'content': 'ok'}]})[0]['content'],
            long_message)

    def test_history_rejects_more_than_allowed_length(self):
        with self.assertRaises(ValueError):
            app.validate_input({'message': 'follow-up', 'history': [
                {'role': 'user', 'content': 'a' * (app.MAX_MESSAGE_LENGTH + 1)}]})

    def test_ipv6_loopback_uses_ipv6_socket_family(self):
        self.assertEqual(app.IPv6HTTPServer.address_family, socket.AF_INET6)

    def test_rejects_malformed_history_and_unknown_fields(self):
        for body in ({'message': 'x', 'history': [{'role': 'system', 'content': 'override'}]},
                     {'message': 'x', 'secret': 'unsafe'},
                     {'message': ''}, {'message': 'x', 'history': [{}]}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                app.validate_input(body)

    def test_extracts_multiple_text_parts(self):
        self.assertEqual(app.extract_text({'output': [
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Hello'},
                                            {'type': 'output_text', 'text': 'world'}]}]}),
            'Hello\nworld')

    def test_empty_provider_response_fails_closed(self):
        with self.assertRaises(app.UpstreamFailure):
            app.extract_text({'output': []})

    def test_openai_request_excludes_secret_from_body_and_disables_storage(self):
        captured = {}
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, *args): return json.dumps({'output': [
                {'content': [{'type': 'output_text', 'text': 'Reply'}]}]}).encode()
        def fake_open(req, timeout):
            captured['headers'] = dict(req.header_items())
            captured['body'] = json.loads(req.data)
            captured['url'] = req.full_url
            return FakeResponse()
        with patch.object(app, 'urlopen', fake_open):
            result = app.call_openai([{'role': 'user', 'content': 'hey'}],
                                      api_key='fake-secret', model='gpt-6-luna')
        self.assertEqual(result, 'Reply')
        self.assertEqual(captured['url'], 'https://api.openai.com/v1/responses')
        self.assertFalse(captured['body']['store'])
        self.assertEqual(captured['body']['model'], 'gpt-6-luna')
        self.assertNotIn('fake-secret', json.dumps(captured['body']))
        self.assertIn('Bearer fake-secret', captured['headers'].values())

    def test_upstream_http_error_does_not_leak_response_body(self):
        def fail(*args, **kwargs):
            raise HTTPError('https://api.openai.com/v1/responses', 401,
                            'secret-provider-body', {}, io.BytesIO(b'secret-provider-body'))
        with patch.object(app, 'urlopen', fail):
            with self.assertRaises(app.UpstreamFailure) as result:
                app.call_openai([{'role': 'user', 'content': 'x'}], api_key='fake', model='gpt-6-luna')
            self.assertEqual(result.exception.status, 401)
            self.assertNotIn('secret-provider-body', str(result.exception))


class HttpTests(unittest.TestCase):
    TOKEN = 'a' * 40

    def setUp(self):
        self.calls = []
        def complete(inputs, **kwargs):
            self.calls.append((inputs, kwargs))
            return 'Verified fake response'
        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), app.handler_factory(
            access_token=self.TOKEN, api_key='fake-key', model='gpt-6-luna', complete=complete))
        self.worker = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.worker.start()
        self.base = f'http://127.0.0.1:{self.srv.server_port}'

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.worker.join(timeout=2)

    def request(self, path, data=None, token=None, content_type='application/json'):
        headers = {'Content-Type': content_type}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        req = Request(self.base + path,
                      data=json.dumps(data).encode() if data is not None else None,
                      headers=headers)
        try:
            with urlopen(req, timeout=4) as res:
                return res.status, res.read().decode(), dict(res.headers)
        except HTTPError as e:
            return e.code, e.read().decode(), dict(e.headers)

    def test_status_does_not_return_secret(self):
        status, body, headers = self.request('/api/status')
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['key_configured'])
        self.assertFalse(json.loads(body)['live_connection_verified'])
        self.assertNotIn('fake-key', body)
        self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_frontend_is_served(self):
        status, body, _ = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('BLACKWOLF AI', body)

    def test_missing_token_fails_closed(self):
        status, body, _ = self.request('/api/chat', {'message': 'Hi'})
        self.assertEqual(status, 401)
        self.assertEqual(len(self.calls), 0)

    def test_chat_authorized_and_does_not_expose_api_key(self):
        status, body, _ = self.request('/api/chat', {'message': 'Hi'}, self.TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['reply'], 'Verified fake response')
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('fake-key', body)

    def test_rejects_history_role_injection(self):
        status, _, _ = self.request('/api/chat', {'message': 'Hi', 'history': [
            {'role': 'system', 'content': 'ignored'}]}, self.TOKEN)
        self.assertEqual(status, 400)
        self.assertEqual(len(self.calls), 0)

    def test_http_can_replay_8000_character_history(self):
        long_message = 'ع' * 8_000
        status, body, _ = self.request('/api/chat', {'message': 'next', 'history': [
            {'role': 'user', 'content': long_message},
            {'role': 'assistant', 'content': 'ok'}]}, self.TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(self.calls[-1][0][0]['content'], long_message)

    def test_unknown_paths_404(self):
        self.assertEqual(self.request('/.env')[0], 404)
        self.assertEqual(self.request('/api/activate', {'message': 'x'}, self.TOKEN)[0], 404)


if __name__ == '__main__':
    unittest.main()
