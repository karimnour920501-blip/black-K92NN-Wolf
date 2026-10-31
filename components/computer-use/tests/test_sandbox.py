import unittest
from wolf_cua.sandbox import Sandbox

class SandboxTests(unittest.TestCase):
    def test_docker_requires_no_network_and_no_mounts(self):
        cmd=Sandbox.docker().command
        self.assertIn('none', cmd)
        self.assertIn('--read-only',cmd)
        self.assertIn('no-new-privileges:true',cmd)
        self.assertNotIn('-v',cmd)
        self.assertNotIn('--env',cmd)
    def test_worker_execution_error_raises_and_kills_process(self):
        """Guest errors must not be treated as successful screenshots."""
        from io import StringIO
        from unittest.mock import MagicMock, patch
        from wolf_cua.sandbox import SandboxError

        worker = MagicMock()
        worker.poll.return_value = None
        worker.stdin = StringIO()
        worker.stdout = StringIO('{"session_id":"s","error":"EXECUTION_FAILED"}\\n')
        sandbox = Sandbox(['mock-worker'])
        sandbox.process = worker

        with patch('wolf_cua.sandbox.select.select',
                   return_value=([worker.stdout], [], [])):
            with self.assertRaisesRegex(SandboxError, 'rejected execution'):
                sandbox.execute('s', "page.goto('https://example.com')")

        worker.kill.assert_called_once()
        self.assertIsNone(sandbox.process)

    def test_bad_image_is_refused(self):
        from wolf_cua.runner import validate_observations
        with self.assertRaises(ValueError):
            validate_observations([{'type':'input_image', 'image_url':'data:image/jpeg;base64,AA', 'detail':'original'}])

if __name__=='__main__': unittest.main()
