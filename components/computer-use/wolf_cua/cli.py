"""Reproducible local rehearsal (no key) and opt-in live Responses API run."""
import argparse
import base64
import json
import os
import secrets
import sys
from pathlib import Path

from .sandbox import Sandbox
from .runner import run_task, verify_badge

STEPS = ["page.locator('#name').fill('Mira')",
         "page.locator('#save').click(); log(page.locator('#result').inner_text())"]
TASK = ("On the isolated local badge page, fill the Name field with Mira, "
        "click Create badge, then report the confirmation. Use exec_py and "
        "include a screenshot. No external websites or logins.")


def write_evidence(output: Path, success: bool, observations: list[dict], mode: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    image = next((i['image_url'].split(',', 1)[1] for i in reversed(observations)
                  if i['type'] == 'input_image'), None)
    if image:
        (output / 'badge-final.png').write_bytes(base64.b64decode(image))
    (output / 'result.json').write_text(json.dumps({'verified': success,
          'mode': mode, 'expected': 'Badge ready: Mira',
          'note': 'Local fixture only; no external UI changes'}, indent=2) + '\n')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Use paid OpenAI Responses API')
    parser.add_argument('--output', type=Path, default=Path('evidence'))
    parser.add_argument('--image', default='wolf-cua-worker:local')
    parser.add_argument('--local-rehearsal', action='store_true',
                        help='Host browser without Docker, NEVER for live API')
    args = parser.parse_args()
    if args.live and args.local_rehearsal:
        parser.error('live API cannot run in unsafe local-rehearsal mode')
    if args.live and not os.getenv('OPENAI_API_KEY'):
        parser.error('OPENAI_API_KEY required only for --live')
    runtime = Sandbox.local_rehearsal() if args.local_rehearsal else Sandbox.docker(args.image)
    session_id = secrets.token_hex(16)
    try:
        with runtime:
            if args.live:
                from openai import OpenAI
                client = OpenAI(timeout=30, max_retries=0)
                def confirm(code: str) -> bool:
                    print('\nProposed Python for isolated fixture:\n' + code + '\n')
                    return input('Approve this exact script? Type yes: ').strip() == 'yes'
                result = run_task(client, runtime, TASK, session_id, confirm)
                print('Model:', result.text)
            else:
                for step in STEPS:
                    runtime.execute(session_id, step)
            verified, observations = verify_badge(runtime, session_id)
            write_evidence(args.output, verified, observations,
                           'live-responses' if args.live else 'scripted-local')
            print(json.dumps({'verified': verified, 'output': str(args.output),
                              'api_used': args.live}))
            return 0 if verified else 1
    except Exception as exc:
        print(f'NOT VERIFIED: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
