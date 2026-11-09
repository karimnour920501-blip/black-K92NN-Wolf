#!/usr/bin/env python3
"""Run only disposable local Docker Compose resources; no cloud/account mutations."""
import datetime,hashlib,json,os,secrets,subprocess,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 project='k92n-ci-'+uuid.uuid4().hex[:12];token=secrets.token_urlsafe(48)
 env=os.environ.copy();env['K92N_OPERATOR_TOKEN']=token
 command=['docker','compose','-p',project,'-f',str(ROOT/'infra/compose.pilot.yaml')]
 checks=[];failure=None
 def run(args):
  r=subprocess.run(args,env=env,capture_output=True,text=True,timeout=180)
  if r.returncode:raise RuntimeError(('Command failed: '+r.stderr[-2000:]).replace(token,'[REDACTED]'))
  return r
 def check(name,value):
  checks.append({'name':name,'status':'PASS' if value else 'FAIL'})
  if not value:raise AssertionError(name)
 try:
  run(['docker','tag','k92n-render:test','k92n-pilot:1.0.2'])
  check('compose syntax and environment valid',run(command+['config','--quiet']).returncode==0)
  check('compose initializes owned volume and starts healthy non-root app',run(command+['up','--no-build','--detach','--wait','--wait-timeout','90']).returncode==0)
  report=ROOT/'evidence/compose-preflight-results.json'
  check('read-only preflight succeeds on Compose app',run([os.sys.executable,str(ROOT/'tools/pilot_preflight.py'),'http://127.0.0.1:5080','--output',str(report)]).returncode==0)
  check('compose app runs non-root',run(command+['exec','-T','web','id','-u']).stdout.strip()!='0')
 except Exception as e:failure=type(e).__name__+': '+str(e).replace(token,'[REDACTED]')
 finally:
  # Only this randomly named CI project's disposable volumes are removed.
  r=subprocess.run(command+['down','--volumes','--remove-orphans'],env=env,capture_output=True,text=True,timeout=60)
  if r.returncode and failure is None:failure='Disposable Compose cleanup failed'
 result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':os.environ.get('GITHUB_SHA'),'scope':'real local Docker Compose + synthetic empty DB; no Render or paid service','compose_sha256':hashlib.sha256((ROOT/'infra/compose.pilot.yaml').read_bytes()).hexdigest(),'checks':checks,'failure':failure,'production_ready':False}
 (ROOT/'evidence/compose-pilot-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks':len(checks),'passed':sum(c['status']=='PASS' for c in checks),'failure':failure}));return 1 if failure else 0
if __name__=='__main__':raise SystemExit(main())
