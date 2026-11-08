#!/usr/bin/env python3
"""Tests startup control flow with fake mountpoint/dotnet, NOT a Docker or cloud test."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Startup(unittest.TestCase):
 def run_case(self,**overrides):
  with tempfile.TemporaryDirectory() as td:
   t=Path(td);m=t/'mount';m.mkdir();b=t/'bin';b.mkdir()
   (b/'mountpoint').write_text('#!/bin/bash\nexit "${TEST_MOUNT_EXIT:-0}"\n')
   (b/'dotnet').write_text('#!/bin/bash\n[[ "$1" == K92N.Host.dll ]] || exit 90\nprintf "EXECUTED %s %s\\n" "$ASPNETCORE_URLS" "$ASPNETCORE_ENVIRONMENT"\n')
   for f in b.iterdir():f.chmod(0o755)
   env=os.environ.copy();env.update(PATH=str(b)+':'+env['PATH'],K92N_OPERATOR_TOKEN='a'*48,K92N_DATA_MOUNT=str(m),K92N_DATA_DIR=str(m/'ledger'),PORT='10000')
   env.update(overrides)
   return subprocess.run(['bash',str(ROOT/'infra/render-entrypoint.sh')],env=env,text=True,capture_output=True)
 def test_valid(self):
  r=self.run_case();self.assertEqual(0,r.returncode,r.stderr);self.assertIn('EXECUTED http://0.0.0.0:10000 Production',r.stdout)
 def test_short_secret(self):self.assertEqual(78,self.run_case(K92N_OPERATOR_TOKEN='short').returncode)
 def test_missing_secret(self):self.assertEqual(78,self.run_case(K92N_OPERATOR_TOKEN='').returncode)
 def test_secret_not_logged(self):
  r=self.run_case(K92N_OPERATOR_TOKEN='sensitive');self.assertNotIn('sensitive',r.stdout+r.stderr)
 def test_no_disk(self):self.assertEqual(78,self.run_case(TEST_MOUNT_EXIT='1').returncode)
 def test_missing_mount(self):self.assertEqual(78,self.run_case(K92N_DATA_MOUNT='/nonexistent-k92n').returncode)
 def test_outside_mount(self):self.assertEqual(78,self.run_case(K92N_DATA_DIR='/tmp').returncode)
 def test_root_mount(self):self.assertEqual(78,self.run_case(K92N_DATA_MOUNT='/').returncode)
 def test_port_zero(self):self.assertEqual(78,self.run_case(PORT='0').returncode)
 def test_port_overflow(self):self.assertEqual(78,self.run_case(PORT='65536').returncode)
 def test_port_injection(self):self.assertEqual(78,self.run_case(PORT='10000;echo oops').returncode)
 def test_leading_zero_port(self):self.assertEqual(0,self.run_case(PORT='08080').returncode)
if __name__=='__main__':unittest.main(verbosity=2)
