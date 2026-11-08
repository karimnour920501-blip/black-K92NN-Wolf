import importlib.util,json,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'tools/k92n.py'
spec=importlib.util.spec_from_file_location('k92n',p);k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)
class ReplayTests(unittest.TestCase):
 def event(self,seq=1,prev='0'*64,kind='decision',entity='ADR-1',payload='{"text":"اعتماد"}'):
  e={'seq':seq,'at':'2026-11-08T00:00:00.000Z','kind':kind,'entityId':entity,'payload':payload,'prevHash':prev}
  e['hash']=k.canon([2,seq,e['at'],kind,entity,payload,prev]);return e
 def test_determinism(self):
  a=self.event();b=self.event(2,a['hash'],payload='{"text":"تحديث"}')
  self.assertEqual(k.replay([a,b]),k.replay([a,b]));self.assertEqual(k.replay([a,b])['projection']['decision:ADR-1']['text'],'تحديث')
 def test_tamper(self):
  e=self.event();e['payload']='{}'
  with self.assertRaises(ValueError):k.replay([e])
 def test_sequence(self):
  with self.assertRaises(ValueError):k.replay([self.event(2)])
 def test_link(self):
  with self.assertRaises(ValueError):k.replay([self.event(prev='1'*64)])
 def test_null_and_empty_differ(self):self.assertNotEqual(k.canon([None]),k.canon(['']))
 def test_field_boundaries(self):self.assertNotEqual(k.canon(['AB','C']),k.canon(['A','BC']))
 def test_utf8_known_vector(self):self.assertEqual(k.canon([2,'كريم',None,100]),'e69def7e30098762a1c0405c820449abd969446fb9a09640f0f655a20ae30b5c')

import sqlite3,tempfile
spec2=importlib.util.spec_from_file_location('backup',p.parent/'backup.py');backup=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(backup)
class BackupTests(unittest.TestCase):
 def test_roundtrip_preserves_rows(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'a.db';b=Path(d)/'b.db';restored=Path(d)/'restored.db'
   with sqlite3.connect(a) as db:db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE records(id INTEGER PRIMARY KEY,text TEXT)');db.execute("INSERT INTO records VALUES(1,'كريم')")
   backup.copy_database(a,b);backup.copy_database(b,restored)
   with sqlite3.connect(restored) as db:self.assertEqual(db.execute('SELECT * FROM records').fetchall(),[(1,'كريم')])
 def test_existing_destination_is_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'a.db';a.write_bytes(b'keep')
   with self.assertRaises(ValueError):backup.copy_database(a,a)
   self.assertEqual(a.read_bytes(),b'keep')
 def test_invalid_source_does_not_publish(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'bad.db';b=Path(d)/'out.db';a.write_bytes(b'not sqlite')
   with self.assertRaises(sqlite3.DatabaseError):backup.copy_database(a,b)
   self.assertFalse(b.exists())
