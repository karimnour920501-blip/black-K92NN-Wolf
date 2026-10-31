"""Responses API tool loop using an application-owned isolated browser worker."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Protocol, Any

TOOL = {
    'type': 'function',
    'name': 'exec_py',
    'description': ('Execute Python with a persistent Playwright browser in an isolated OFFLINE '
                    'fixture; available: browser, context, page, log(value), display(PNG_bytes). '
                    'Inspect the page and screenshot; no external accounts or networks. '
                    'Do not read or write files. Calls share the same page and Python namespace.'),
    'parameters': {'type': 'object', 'properties': {'code': {'type': 'string'}},
                   'required': ['code'], 'additionalProperties': False},
    'strict': True,
}


class Runtime(Protocol):
    def execute(self, session_id: str, code: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Result:
    text: str
    response_id: str
    turns: int
    calls: int


def validate_observations(items: Any) -> list[dict]:
    if not isinstance(items, list) or not items or len(items) > 8:
        raise ValueError('sandbox observations invalid')
    valid = []
    has_image = False
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('observation must be object')
        if item.get('type') == 'input_text' and isinstance(item.get('text'), str):
            valid.append({'type': 'input_text', 'text': item['text'][:12000]})
        elif item.get('type') == 'input_image' and item.get('detail') == 'original' and isinstance(item.get('image_url'), str) and item['image_url'].startswith('data:image/png;base64,'):
            if len(item['image_url']) > 7_000_000:
                raise ValueError('image too large')
            has_image = True
            valid.append({'type': 'input_image', 'image_url': item['image_url'], 'detail': 'original'})
        else:
            raise ValueError('unknown observation item')
    if not has_image:
        raise ValueError('sandbox must return fresh screenshot')
    return valid


def run_task(client: Any, runtime: Runtime, task: str, session_id: str,
             approve: Callable[[str], bool], *, model: str = 'gpt-6-astra',
             max_turns: int = 6) -> Result:
    if not 1 <= max_turns <= 20:
        raise ValueError('max_turns must be in [1,20]')
    if not task.strip() or not session_id.strip():
        raise ValueError('task and session_id required')
    conversation: list[dict] = [{'role': 'user', 'content': task}]
    previous_id = None
    calls_done = 0
    for turn in range(1, max_turns + 1):
        request = {'model': model, 'tools': [TOOL], 'tool_choice': 'auto',
                   'parallel_tool_calls': False, 'input': conversation}
        if previous_id:
            request['previous_response_id'] = previous_id
        response = client.responses.create(**request)
        if response.status != 'completed':
            raise RuntimeError('model response not completed; no actions executed')
        generated = [x for x in response.output if x.type == 'function_call']
        if not generated:
            if not getattr(response, 'output_text', ''):
                raise RuntimeError('model returned no final text')
            return Result(response.output_text, response.id, turn, calls_done)
        if turn == max_turns:
            raise RuntimeError('turn limit reached; unexecuted tool calls refused')
        outputs = []
        for call in generated:
            if call.name != 'exec_py':
                raise RuntimeError('unexpected function call refused')
            try:
                payload = json.loads(call.arguments)
            except (TypeError, ValueError) as exc:
                raise ValueError('malformed tool arguments') from exc
            if set(payload) != {'code'} or not isinstance(payload['code'], str) or len(payload['code']) > 12000:
                raise ValueError('invalid code argument')
            code = payload['code']
            if approve(code) is not True:
                observation = [{'type': 'input_text', 'text': 'User declined this tool execution.'}]
            else:
                observation = validate_observations(runtime.execute(session_id, code)['output'])
                calls_done += 1
            outputs.append({'type': 'function_call_output',
                            'call_id': call.call_id, 'output': observation})
        previous_id = response.id
        conversation = outputs
    raise RuntimeError('unreachable')


def verify_badge(runtime: Runtime, session_id: str) -> tuple[bool, list[dict]]:
    """Independently inspect the actual local fixture after model or scripted steps."""
    observed = runtime.execute(session_id, "log(page.locator('#result').inner_text())")
    items = validate_observations(observed['output'])
    return (bool(items and items[0]['type'] == 'input_text' and
                 items[0]['text'].strip() == 'Badge ready: Mira'), items)
