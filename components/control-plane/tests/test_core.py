import tempfile, unittest
from pathlib import Path
from control_plane import ControlPlane
class TestControlPlane(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.cp=ControlPlane(Path(self.tmp.name)/'db.sqlite')
    def tearDown(self):self.cp.close();self.tmp.cleanup()
    def test_projects(self):
        self.cp.register_project('wolf','Black Wolf','https://github.com/example/repo')
        self.assertEqual(self.cp.inventory()['projects'][0]['status'],'DISCOVERED')
    def test_connectors_disabled(self):
        self.cp.register_connector('gh','github')
        self.assertEqual(self.cp.inventory()['connectors'][0]['enabled'],0)
    def test_default_deny(self):self.assertEqual(self.cp.authorize('read_secret'),'deny')
    def test_read_policy(self):
        self.cp.set_policy('r','read_inventory','allow')
        self.assertEqual(self.cp.authorize('read_inventory'),'allow')
    def test_writes_always_denied(self):
        self.cp.set_policy('w','delete_repository','allow')
        self.assertEqual(self.cp.authorize('delete_repository'),'deny')
    def test_audit_chain(self):
        self.cp.register_project('a','A');self.cp.register_connector('g','github')
        self.assertTrue(self.cp.verify_audit())
    def test_tamper_detection(self):
        self.cp.register_project('a','A')
        self.cp.db.execute("UPDATE audit SET outcome='forged' WHERE seq=1");self.cp.db.commit()
        self.assertFalse(self.cp.verify_audit())
if __name__=='__main__':unittest.main()
