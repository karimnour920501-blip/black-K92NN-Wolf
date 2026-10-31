"""True Playwright+Responses-loop rehearsal with a scripted mock model, no API."""
import base64
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace

from wolf_cua.runner import run_task, verify_badge
from wolf_cua.sandbox import Sandbox, SandboxError


def tool_response(response_id, call_id, code):
    return SimpleNamespace(
        id=response_id, status='completed', output_text='',
        output=[SimpleNamespace(type='function_call', name='exec_py',
                                call_id=call_id,
                                arguments=json.dumps({'code': code}))],
    )


class FakeApi:
    def __init__(self):
        self.requests = []
        self.answers = iter([
            tool_response('resp-1','call-1',"page.locator('#name').fill('Mira')"),
            tool_response('resp-2','call-2',"page.locator('#save').click(); log(page.locator('#result').inner_text())"),
            SimpleNamespace(id='resp-3', status='completed', output_text='Badge ready: Mira', output=[]),
        ])

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return next(self.answers)


class BrowserLoopRehearsal(unittest.TestCase):
    def test_live_browser_with_mock_responses_loop(self):
        api = FakeApi()
        with Sandbox.local_rehearsal() as sandbox:
            result = run_task(SimpleNamespace(responses=api), sandbox,
                              'Create a fictional visitor badge for Mira', 'rehearsal-session',
                              lambda _code: True, max_turns=5)
            passed, observations = verify_badge(sandbox, 'rehearsal-session')
        self.assertTrue(passed)
        self.assertEqual(result.calls, 2)
        self.assertEqual(result.turns, 3)
        self.assertEqual(api.requests[1]['input'][0]['call_id'], 'call-1')
        self.assertEqual(api.requests[2]['input'][0]['call_id'], 'call-2')
        self.assertTrue(api.requests[2]['input'][0]['output'][-1]['image_url'].startswith('data:image/png;base64,'))
        self.assertGreater(len(base64.b64decode(observations[-1]['image_url'].split(',')[1])), 3000)


    def test_persistent_python_namespace_and_external_navigation_blocked(self):
        with Sandbox.local_rehearsal() as sandbox:
            first = sandbox.execute('same-session', 'run_counter = 40')
            second = sandbox.execute('same-session', 'run_counter += 2; log(run_counter)')
            with self.assertRaisesRegex(SandboxError, 'rejected execution'):
                sandbox.execute('same-session',
                                "page.goto('https://example.com'); log('unexpected')")
            # A rejected browser action must invalidate the worker session.
            with self.assertRaisesRegex(SandboxError, 'not running'):
                sandbox.execute('same-session', "log('should not run')")
        self.assertEqual(second['output'][0]['text'].strip(), '42')


if __name__ == '__main__': unittest.main()
