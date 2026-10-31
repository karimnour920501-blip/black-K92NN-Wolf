"""Local-only BLACKWOLF AI chat gateway. Python 3.10+, stdlib only.

No OpenAI API key is ever sent to the browser. This service is not an
internet-facing authentication gateway; deploy behind hardened auth + TLS.
"""
import argparse
import hmac
import json
import os
import secrets
import socket
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL_DEFAULT = 'gpt-6-luna'
MAX_BODY_BYTES = 40_000
MAX_MESSAGE_LENGTH = 8_000
MAX_HISTORY = 8
MAX_REPLY_TOKENS = 1024
SYSTEM_INSTRUCTIONS = (
    'You are BLACKWOLF AI for the BLACK-K92N-WOLF project. Answer in the '
    'user\'s language. Provide concrete, cautious software engineering '
    'assistance for C#/.NET, Python, SaaS, and systems architecture. '
    'Distinguish implemented, tested and planned work. Never invent '
    'deployments, credentials, test results or tool execution. Never '
    'claim that you can modify an external system without evidence.'
)
HTML_PATH = Path(__file__).with_name('index.html')


class UpstreamFailure(Exception):
    def __init__(self, status=None):
        self.status = status


def validate_input(body):
    if not isinstance(body, dict) or set(body) - {'message', 'history'}:
        raise ValueError('invalid_request')
    message = body.get('message')
    if not isinstance(message, str) or not message.strip() or len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError('invalid_message')
    history = body.get('history', [])
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        raise ValueError('invalid_history')
    inputs = []
    for item in history:
        if (not isinstance(item, dict) or set(item) != {'role', 'content'}
                or item['role'] not in ('user', 'assistant')
                or not isinstance(item['content'], str)
                or not item['content'].strip()
                or len(item['content']) > MAX_MESSAGE_LENGTH):
            raise ValueError('invalid_history')
        inputs.append({'role': item['role'], 'content': item['content']})
    inputs.append({'role': 'user', 'content': message})
    return inputs


def extract_text(data):
    parts = []
    for item in data.get('output', []):
        if not isinstance(item, dict):
            continue
        for content in item.get('content', []):
            if isinstance(content, dict) and content.get('type') == 'output_text':
                text = content.get('text')
                if isinstance(text, str):
                    parts.append(text)
    result = '\n'.join(parts).strip()
    if not result:
        raise UpstreamFailure()
    return result


def call_openai(inputs, *, api_key, model, project_id=None):
    body = {
        'model': model,
        'instructions': SYSTEM_INSTRUCTIONS,
        'input': inputs,
        'max_output_tokens': MAX_REPLY_TOKENS,
        'store': False,
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    if project_id:
        headers['OpenAI-Project'] = project_id
    request = Request('https://api.openai.com/v1/responses',
                      data=json.dumps(body).encode('utf-8'),
                      headers=headers, method='POST')
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
        if not isinstance(payload, dict):
            raise UpstreamFailure()
        return extract_text(payload)
    except HTTPError as exc:
        raise UpstreamFailure(exc.code) from None
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise UpstreamFailure() from None


class RateLimiter:
    """Small per-process guardrail; not a distributed production rate limit."""
    def __init__(self, limit=10, window=60):
        self.limit = limit
        self.window = window
        self.events = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, address):
        with self.lock:
            now = time.monotonic()
            q = self.events[address]
            while q and q[0] <= now - self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


def handler_factory(*, access_token, api_key, model, project_id=None, complete=call_openai, rate_limiter=None):
    limiter = rate_limiter or RateLimiter()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Do not log query strings, messages, Authorization or provider errors.
            pass

        def send_json(self, status, payload):
            self.send_bytes(status, json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                            'application/json; charset=utf-8')

        def send_bytes(self, status, data, mime):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ('/', '/index.html'):
                return self.send_bytes(200, HTML_PATH.read_bytes(), 'text/html; charset=utf-8')
            if self.path == '/api/status':
                return self.send_json(200, {'service': 'BLACKWOLF AI',
                                            'key_configured': bool(api_key),
                                            'model': model,
                                            'live_connection_verified': False})
            if self.path == '/health':
                return self.send_json(200, {'status': 'process_healthy'})
            self.send_json(404, {'error': 'not_found'})

        def do_POST(self):
            if self.path != '/api/chat':
                return self.send_json(404, {'error': 'not_found'})
            raw_token = self.headers.get('Authorization', '')
            if not hmac.compare_digest(raw_token, f'Bearer {access_token}'):
                return self.send_json(401, {'error': 'unauthorized'})
            if not api_key:
                return self.send_json(503, {'error': 'openai_key_not_configured'})
            if not limiter.allow(self.client_address[0]):
                return self.send_json(429, {'error': 'rate_limited'})
            if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                return self.send_json(415, {'error': 'json_required'})
            try:
                n = int(self.headers.get('Content-Length', '0'))
                if not 0 < n <= MAX_BODY_BYTES:
                    return self.send_json(413, {'error': 'invalid_body_size'})
                body = json.loads(self.rfile.read(n))
                inputs = validate_input(body)
            except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                return self.send_json(400, {'error': 'invalid_request'})
            try:
                answer = complete(inputs, api_key=api_key, model=model, project_id=project_id)
            except UpstreamFailure as exc:
                return self.send_json(502, {'error': 'openai_unavailable', 'upstream_status': exc.status})
            except Exception:
                return self.send_json(502, {'error': 'openai_unavailable'})
            self.send_json(200, {'reply': answer, 'model': model})

    return Handler


class IPv6HTTPServer(ThreadingHTTPServer):
    """Use an IPv6 socket for the explicitly permitted IPv6 loopback host."""
    address_family = socket.AF_INET6


def main():
    p = argparse.ArgumentParser(description='BLACKWOLF AI local chat preview')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8787)
    args = p.parse_args()
    if args.host not in ('127.0.0.1', '::1', 'localhost'):
        p.error('Loopback-only preview. Do not bind to a public interface.')
    token = os.getenv('BLACKWOLF_ACCESS_TOKEN', '')
    if len(token) < 32:
        p.error('Set BLACKWOLF_ACCESS_TOKEN to a random string of at least 32 characters')
    api_key = os.getenv('OPENAI_API_KEY', '')
    model = os.getenv('OPENAI_MODEL', MODEL_DEFAULT)
    project_id = os.getenv('OPENAI_PROJECT_ID')
    server_type = IPv6HTTPServer if args.host == '::1' else ThreadingHTTPServer
    server = server_type((args.host, args.port), handler_factory(
        access_token=token, api_key=api_key, model=model, project_id=project_id))
    address = f'[{args.host}]' if args.host == '::1' else args.host
    print(f'BLACKWOLF AI local preview: http://{address}:{args.port}', flush=True)
    if not api_key:
        print('OPENAI_API_KEY not configured; /api/chat is disabled.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
