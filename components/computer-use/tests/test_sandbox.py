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
    def test_bad_image_is_refused(self):
        from wolf_cua.runner import validate_observations
        with self.assertRaises(ValueError):
            validate_observations([{'type':'input_image', 'image_url':'data:image/jpeg;base64,AA', 'detail':'original'}])

if __name__=='__main__': unittest.main()
