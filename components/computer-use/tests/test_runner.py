import base64
import json
import unittest
from types import SimpleNamespace

from wolf_cua.runner import run_task, validate_observations, verify_badge

PNG = 'data:image/png;base64,' + base64.b64encode(b'fake-png').decode()


class StubSandbox:
    def __init__(self):
        self.actions = []
    def execute(self, session_id, code):
        self.actions.append((session_id, code))
        text = 'Badge ready: Mira' if "#result" in code else 'ok'
        return {'output': [{'type': 'input_text', 'text': text},
                           {'type': 'input_image', 'image_url': PNG, 'detail': 'original'}]}


class StubResponses:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []
    def create(self, **kwargs):
        self.requests.append(kwargs)
        return next(self.responses)


def call():
    return SimpleNamespace(id='resp1', status='completed', output_text='',
        output=[SimpleNamespace(type='function_call', name='exec_py',
             call_id='call-42', arguments=json.dumps({'code': "page.locator('#name').fill('Mira')"}))])


def finish():
    return SimpleNamespace(id='resp2', status='completed',
                           output_text='Badge created', output=[])


class LoopTests(unittest.TestCase):
    def test_tool_loop_and_image_and_call_id(self):
        api = StubResponses([call(), finish()])
        runtime = StubSandbox()
        result = run_task(SimpleNamespace(responses=api), runtime, 'Create badge',
                          'session-1', lambda _: True)
        self.assertEqual(result.calls, 1)
        self.assertEqual(result.turns, 2)
        self.assertEqual(api.requests[1]['previous_response_id'], 'resp1')
        self.assertEqual(api.requests[1]['input'][0]['call_id'], 'call-42')
        self.assertEqual(api.requests[1]['input'][0]['output'][1]['detail'], 'original')
        self.assertEqual(runtime.actions[0][0], 'session-1')

    def test_refusal_does_not_execute(self):
        api = StubResponses([call(), finish()]); runtime = StubSandbox()
        result = run_task(SimpleNamespace(responses=api), runtime,
                          'No change', 'session-2', lambda _: False)
        self.assertEqual(result.calls, 0)
        self.assertEqual(runtime.actions, [])
        self.assertIn('declined', api.requests[1]['input'][0]['output'][0]['text'])

    def test_fails_closed_on_incomplete_response(self):
        api = StubResponses([SimpleNamespace(id='resp1', status='incomplete', output=[])])
        with self.assertRaises(RuntimeError):
            run_task(SimpleNamespace(responses=api), StubSandbox(),
                     'Create badge', 's', lambda _: True)

    def test_limit_never_executes_final_turn(self):
        api = StubResponses([call()])
        with self.assertRaises(RuntimeError):
            run_task(SimpleNamespace(responses=api), StubSandbox(),
                     'Create badge', 's', lambda _: True, max_turns=1)

    def test_rejects_missing_or_malformed_image(self):
        for items in [[], [{'type':'input_text','text':'ok'}],
                      [{'type':'input_image','image_url':'https://example.com','detail':'original'}]]:
            with self.assertRaises(ValueError): validate_observations(items)

    def test_independent_verification(self):
        valid, items = verify_badge(StubSandbox(), 'session-2')
        self.assertTrue(valid)
        self.assertEqual(items[-1]['detail'], 'original')


if __name__ == '__main__': unittest.main()
