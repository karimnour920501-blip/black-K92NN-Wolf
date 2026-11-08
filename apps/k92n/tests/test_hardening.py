"""Negative tests for recovery safety and build policy. Fixtures are isolated."""
import base64,contextlib,hashlib,importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
backup=module('backup_hardening',ROOT/'tools/backup.py')
supply=module('supply_hardening',ROOT/'tools/verify_supply_chain.py')
class RestoreSafety(unittest.TestCase):
 def test_existing_target_unchanged(self):
  with tempfile.TemporaryDirectory() as td:
   s=Path(td)/'source';t=Path(td)/'target';s.write_bytes(b'invalid');t.write_bytes(b'keep')
   with self.assertRaises(ValueError):backup.restore_database(s,t)
   self.assertEqual(t.read_bytes(),b'keep')
 def test_corruption_does_not_publish(self):
  with tempfile.TemporaryDirectory() as td:
   s=Path(td)/'source';t=Path(td)/'target';s.write_bytes(b'corrupted bytes')
   with self.assertRaises(sqlite3.DatabaseError):backup.restore_database(s,t)
   self.assertFalse(t.exists());self.assertEqual(s.read_bytes(),b'corrupted bytes')
 def test_live_wal_input_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   s=Path(td)/'source';t=Path(td)/'target'
   with contextlib.closing(sqlite3.connect(s)) as db:
    db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE t(id INTEGER)');db.commit()
    with self.assertRaisesRegex(ValueError,'standalone backup'):backup.restore_database(s,t)
    self.assertFalse(t.exists());self.assertEqual(db.execute('SELECT COUNT(*) FROM t').fetchone()[0],0)
 def test_wrong_checksum_does_not_publish(self):
  with tempfile.TemporaryDirectory() as td:
   s=Path(td)/'source';t=Path(td)/'target'
   with contextlib.closing(sqlite3.connect(s)) as db:db.execute('CREATE TABLE t(id INTEGER)');db.commit()
   with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):backup.restore_database(s,t,'0'*64)
   self.assertFalse(t.exists())
 def test_foreign_key_violation_does_not_publish(self):
  with tempfile.TemporaryDirectory() as td:
   s=Path(td)/'source';t=Path(td)/'target'
   with contextlib.closing(sqlite3.connect(s)) as db:
    db.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(p INTEGER REFERENCES parent(id)); INSERT INTO child VALUES(7);')
   with self.assertRaisesRegex(ValueError,'foreign_key_check'):backup.restore_database(s,t)
   self.assertFalse(t.exists())
 def test_standalone_restore_preserves_rows(self):
  with tempfile.TemporaryDirectory() as td:
   s=Path(td)/'source';t=Path(td)/'target'
   with contextlib.closing(sqlite3.connect(s)) as db:db.execute('CREATE TABLE t(id INTEGER)');db.execute('INSERT INTO t VALUES(7)');db.commit()
   backup.restore_database(s,t,backup.file_sha256(s))
   with contextlib.closing(sqlite3.connect(t)) as db:self.assertEqual(db.execute('SELECT id FROM t').fetchall(),[(7,)])
class SupplyPolicy(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.repo=Path(self.temp.name);self.root=self.repo/'apps/k92n'
  for path in ['infra/supply-chain-lock.json','infra/Dockerfile.render','Directory.Build.props','NuGet.Config','package.json','package-lock.json','.npmrc']:
   dest=self.root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/path).read_bytes())
  self.workflow=self.repo/'.github/workflows/k92n-hosting-verify.yml';self.workflow.parent.mkdir(parents=True);self.workflow.write_bytes((ROOT.parents[1]/'.github/workflows/k92n-hosting-verify.yml').read_bytes())
  self.old_root=supply.ROOT;self.old_repo=supply.REPO;supply.ROOT=self.root;supply.REPO=self.repo
 def tearDown(self):supply.ROOT=self.old_root;supply.REPO=self.old_repo;self.temp.cleanup()
 def test_pinned_policy_accepts_baseline(self):self.assertEqual(len(supply.verify_pins()['actions']),3)
 def test_mutable_action_rejected(self):
  import re
  self.workflow.write_text(re.sub(r'actions/checkout@[a-f0-9]{40}','actions/checkout@main',self.workflow.read_text()))
  with self.assertRaises(ValueError):supply.verify_pins()
 def test_wrong_image_digest_rejected(self):
  f=self.root/'infra/Dockerfile.render';f.write_text(f.read_text().replace('@sha256:','@sha256:0',1))
  with self.assertRaises(ValueError):supply.verify_pins()
 def test_unlocked_restore_rejected(self):
  f=self.root/'Directory.Build.props';f.write_text(f.read_text().replace('<RestoreLockedMode>true','<RestoreLockedMode>false'))
  with self.assertRaises(ValueError):supply.verify_pins()
 def test_extra_package_source_rejected(self):
  f=self.root/'NuGet.Config';f.write_text(f.read_text().replace('</packageSources>','<add key="other" value="https://invalid.example/" /></packageSources>'))
  with self.assertRaises(ValueError):supply.verify_pins()
 def audit(self,data):
  f=self.repo/'audit.json';f.write_text(json.dumps(data));return supply.verify_audit(f)
 def test_missing_audit_graph_rejected(self):
  with self.assertRaises(ValueError):self.audit({'version':1,'projects':[]})
 def test_audit_warning_not_green(self):
  with self.assertRaises(ValueError):self.audit({'version':1,'projects':[{'frameworks':[{'framework':'net10.0'}]}],'logs':[{'level':'Warning','message':'advisories unavailable'}]})
 def test_vulnerable_package_not_green(self):
  with self.assertRaises(ValueError):self.audit({'version':1,'projects':[{'frameworks':[{'framework':'net10.0','transitivePackages':[{'id':'bad','vulnerabilities':[{'severity':'High'}]}]}]}]})
 def test_clean_audit_accepted(self):self.assertEqual(self.audit({'version':1,'projects':[{'frameworks':[{'framework':'net10.0'}]}]})['known_package_vulnerabilities_reported'],0)


local=module('pilot_local_tests',ROOT/'tools/pilot_local.py')
class LocalOperatorSecret(unittest.TestCase):
 def test_generated_secret_is_private_and_reused(self):
  import stat
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'token';a=local.operator_secret(p);b=local.operator_secret(p)
   self.assertGreaterEqual(len(a),32);self.assertEqual(a,b);self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
 def test_shared_secret_file_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'token';p.write_text('x'*48);p.chmod(0o644)
   with self.assertRaises(ValueError):local.operator_secret(p)
 def test_symlink_secret_rejected_without_modifying_target(self):
  with tempfile.TemporaryDirectory() as td:
   target=Path(td)/'real';target.write_text('x'*48);target.chmod(0o600);link=Path(td)/'token';link.symlink_to(target)
   with self.assertRaises(ValueError):local.operator_secret(link)
   self.assertEqual(target.read_text(),'x'*48)
