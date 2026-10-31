"""Container-owned, bounded JSONL transport. API credentials remain on host."""
from __future__ import annotations

import json
import os
import select
import subprocess
import sys
from dataclasses import dataclass


class SandboxError(RuntimeError):
    pass


@dataclass
class Sandbox:
    command: list[str]
    timeout_seconds: int = 15
    env: dict[str, str] | None = None

    def __post_init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None

    @classmethod
    def docker(cls, image: str = 'wolf-cua-worker:local') -> 'Sandbox':
        # Network=none and no mounted files/keys/Docker socket by construction.
        if not image or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_:/@' for c in image):
            raise ValueError('invalid image name')
        return cls(['docker', 'run', '--rm', '-i', '--network', 'none',
                    '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                    '--pids-limit', '96', '--memory', '768m', '--cpus', '1',
                    '--tmpfs', '/tmp:rw,noexec,nosuid,size=192m',
                    '--tmpfs', '/home/cua:rw,noexec,nosuid,size=64m',
                    '--user', '10001:10001', image], timeout_seconds=20)

    @classmethod
    def local_rehearsal(cls) -> 'Sandbox':
        return cls([sys.executable, '-m', 'wolf_cua.worker'],
                   env={**os.environ, 'WOLF_CUA_LOCAL_REHEARSAL': '1'},
                   timeout_seconds=15)

    def __enter__(self) -> 'Sandbox':
        self.process = subprocess.Popen(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1, env=self.env,
        )
        return self

    def execute(self, session_id: str, code: str) -> dict:
        process = self.process
        if process is None or process.poll() is not None or process.stdin is None or process.stdout is None:
            raise SandboxError('isolated worker is not running')
        request = {'session_id': session_id, 'language': 'python', 'code': code}
        try:
            process.stdin.write(json.dumps(request, ensure_ascii=False) + '\n')
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self.close()
            raise SandboxError('sandbox stream unavailable') from exc
        readable, _, _ = select.select([process.stdout], [], [], self.timeout_seconds)
        if not readable:
            self.close()
            raise SandboxError('execution deadline exceeded; worker terminated')
        line = process.stdout.readline(10_000_000)
        if not line or len(line) >= 10_000_000:
            self.close()
            raise SandboxError('sandbox output missing or too large')
        try:
            result = json.loads(line)
        except json.JSONDecodeError as exc:
            self.close()
            raise SandboxError('malformed sandbox reply') from exc
        if result.get('session_id') != session_id or not isinstance(result.get('output'), list):
            raise SandboxError('sandbox returned error or mismatched session')
        return result

    def close(self) -> None:
        if self.process:
            if self.process.poll() is None:
                self.process.kill()
            try:
                self.process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.communicate()
            self.process = None

    def __exit__(self, *exc: object) -> None:
        self.close()
