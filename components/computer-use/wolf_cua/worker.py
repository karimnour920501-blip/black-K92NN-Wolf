"""JSON-lines Playwright worker. Run ONLY inside the isolated, offline container.

The worker executes model-generated Python; Python globals are NOT a security
boundary. The container/VM and external approval policy are mandatory.
"""
from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright

# No external assets, navigation, live accounts, or credentials in this exercise.
FIXTURE = """<!doctype html><html><head><title>WOLF local badge rehearsal</title></head>
<body><main><h1>BLACK-K92N-WOLF — isolated local fixture</h1>
<label for='name'>Name</label><input id='name' autocomplete='off'>
<button id='save'>Create badge</button><output id='result' aria-live='polite'></output>
</main><script>
document.getElementById('save').addEventListener('click', () => {
  const name = document.getElementById('name').value;
  document.getElementById('result').textContent = 'Badge ready: ' + name;
});
</script></body></html>"""


def screenshot_item(image: bytes) -> dict[str, str]:
    return {
        'type': 'input_image',
        'image_url': 'data:image/png;base64,' + base64.b64encode(image).decode('ascii'),
        'detail': 'original',
    }


def main() -> int:
    # A local rehearsal may explicitly use the host's Chromium. Never use this
    # override for live model-controlled execution or as evidence of isolation.
    rehearsal = os.environ.get('WOLF_CUA_LOCAL_REHEARSAL') == '1'
    if not rehearsal and not os.path.exists('/.dockerenv'):
        raise RuntimeError('Worker refuses unsandboxed execution outside Docker')
    with sync_playwright() as p:
        kw: dict[str, Any] = {'headless': True, 'env': {}}
        if rehearsal:
            explicit_chromium = os.getenv('WOLF_CUA_CHROMIUM')
            if explicit_chromium:
                kw['executable_path'] = explicit_chromium
            elif os.path.exists('/usr/bin/chromium'):
                kw['executable_path'] = '/usr/bin/chromium'
        # Docker is the execution security boundary; Chromium process sandbox
        # may be unavailable under container seccomp. No network is allowed.
        browser = p.chromium.launch(**kw)
        context = browser.new_context(viewport={'width': 1440, 'height': 900},
                                      accept_downloads=False, service_workers='block')
        context.route('**/*', lambda route: route.abort())
        page = context.new_page()
        page.set_content(FIXTURE)
        namespace: dict[str, Any] = {'browser': browser, 'context': context,
                                     'page': page, 'time': time}
        try:
            for line in sys.stdin:
                try:
                    request = json.loads(line)
                    if set(request) != {'session_id', 'language', 'code'}:
                        raise ValueError('invalid request fields')
                    if request['language'] != 'python':
                        raise ValueError('only python code is supported')
                    if not isinstance(request['session_id'], str) or not request['session_id']:
                        raise ValueError('invalid session')
                    if not isinstance(request['code'], str) or len(request['code']) > 12000:
                        raise ValueError('code is empty, invalid or too large')
                    observations: list[dict[str, str]] = []
                    logs: list[str] = []
                    def log(value: Any) -> None:
                        logs.append(str(value)[:3000])
                    def display(image: bytes) -> None:
                        if not isinstance(image, bytes) or len(image) > 5_000_000:
                            raise ValueError('display requires PNG bytes <=5MB')
                        observations.append(screenshot_item(image))
                    namespace.update({'log': log, 'display': display})
                    redirected = io.StringIO()
                    try:
                        with contextlib.redirect_stdout(redirected), contextlib.redirect_stderr(redirected):
                            exec(compile(request['code'], '<model-exec>', 'exec'), namespace, namespace)
                    except Exception as exc:
                        logs.append(f'EXECUTION_FAILED: {type(exc).__name__}')
                    combined = (redirected.getvalue() + '\n'.join(logs))[:12000]
                    observations.insert(0, {'type': 'input_text', 'text': combined or 'ok'})
                    # Always send a fresh screenshot after the action batch.
                    observations.append(screenshot_item(page.screenshot(type='png')))
                    reply = {'session_id': request['session_id'], 'output': observations}
                except Exception as exc:
                    reply = {'error': type(exc).__name__}
                print(json.dumps(reply, ensure_ascii=False, separators=(',', ':')), flush=True)
        finally:
            context.close()
            browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
