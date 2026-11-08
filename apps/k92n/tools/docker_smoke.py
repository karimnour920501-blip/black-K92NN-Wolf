#!/usr/bin/env python3
"""Real disposable Docker volume + HTTP + restart/recreate persistence checks."""
import hashlib,json,os,secrets,socket,subprocess,tempfile,time,urllib.error,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 image=os.environ.get('K92N_TEST_IMAGE','k92n-render:test');suffix=uuid.uuid4().hex[:12]
 volume='k92n-test-'+suffix;original_volume=volume;restored_volume=volume+'-restored';name='k92n-test-'+suffix;token=secrets.token_urlsafe(40)
 env=os.environ.copy();env['K92N_OPERATOR_TOKEN']=token
 checks=[];failure=None
 def docker(*args,ok=True):
  r=subprocess.run(['docker',*args],env=env,text=True,capture_output=True,timeout=120)
  if ok and r.returncode:raise RuntimeError('Docker '+args[0]+' failed: '+r.stderr[:1000])
  return r
 def check(n,c):
  checks.append({'name':n,'status':'PASS' if c else 'FAIL'})
  if not c:raise AssertionError(n)
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 origin=f'http://127.0.0.1:{port}'
 def req(path,body=None,auth=True):
  h={'Authorization':'Bearer '+token} if auth else {}
  data=None
  if body is not None:data=json.dumps(body).encode();h['Content-Type']='application/json'
  try:
   with urllib.request.urlopen(urllib.request.Request(origin+path,data=data,headers=h),timeout=5) as r:return r.status,json.loads(r.read())
  except urllib.error.HTTPError as e:return e.code,{}
 def ready():
  for _ in range(100):
   try:
    if req('/healthz',auth=False)[0]==200:return
   except (urllib.error.URLError,ConnectionError,TimeoutError):pass
   time.sleep(.2)
  raise RuntimeError('container HTTP did not become ready')
 def start():
  docker('run','-d','--name',name,'-p',f'127.0.0.1:{port}:10000','-e','K92N_OPERATOR_TOKEN','-e','PORT=10000','-v',volume+':/data',image)
  ready()
 try:
  # No persistent disk must reject startup, not create an ephemeral ledger.
  r=docker('run','--rm','-e','K92N_OPERATOR_TOKEN',image,ok=False)
  check('missing persistent disk rejects container startup',r.returncode==78 and 'persistent disk is not mounted' in r.stderr)
  docker('volume','create',volume)
  # Initialize ownership of this DISPOSABLE CI volume only. Main app stays non-root.
  docker('run','--rm','--user','0','--entrypoint','bash','-v',volume+':/data',image,'-c','chown app:app /data && chmod 700 /data')
  start()
  check('runtime non-root',docker('exec',name,'id','-u').stdout.strip()!='0')
  check('runtime shell available',docker('exec',name,'bash','-c','test -d "$HOME/.ssh" && test "$(stat -c %a "$HOME/.ssh")" = 700').returncode==0)
  check('health reports production false',req('/healthz',auth=False)[1]['productionReady'] is False)
  check('unauthenticated API rejected',req('/api/status',auth=False)[0]==401)
  for i in [1,2]:check('create account '+str(i),req('/api/accounts',{'id':i,'code':str(i),'name':'CI account'})[0]==201)
  entry={'entryDate':'2026-11-08','description':'Docker CI test','currencyCode':'USD','entryType':'ADJUSTMENT','idempotencyKey':'docker-ci-1','lines':[{'accountId':1,'currencyCode':'USD','debitOrig':10,'creditOrig':0,'debitBase':10,'creditBase':0,'customerId':7},{'accountId':2,'currencyCode':'USD','debitOrig':0,'creditOrig':10,'debitBase':0,'creditBase':10}]}
  status,result=req('/api/journal_entries',entry);check('real container posting',status==200);entry_id=result['id']
  status,result=req('/api/integrity');check('container ledger integrity',status==200 and result['isValid'] and result['entriesChecked']==1);head=result['headHash']
  docker('restart',name);ready()
  status,result=req('/api/integrity');check('restart preserves count and hash',status==200 and result['isValid'] and result['entriesChecked']==1 and result['headHash']==head)
  docker('rm','-f',name);start()
  status,result=req('/api/integrity');check('recreated container preserves volume data',status==200 and result['isValid'] and result['headHash']==head and result['entriesChecked']==1)
  status,result=req('/api/journal_entries',entry);check('idempotency survives recreation',status==200 and result['id']==entry_id)
  docker('exec',name,'python3','/app/tools/backup.py','backup','/data/k92n/k92n-local.db','/data/k92n/ci-backup.db')
  check('SQLite backup works inside image',docker('exec',name,'test','-s','/data/k92n/ci-backup.db').returncode==0)
  # Transfer the actual backup OUT of the source container, then restore on the host.
  golden=req('/api/integrity')[1];golden_balances=req('/api/customers/7/balances?accountId=1')[1]
  check('nonzero customer balance for recovery',golden_balances=={'USD':1000})
  with tempfile.TemporaryDirectory(prefix='k92n-off-container-') as td:
   transfer=Path(td);backup=transfer/'transport.db'
   docker('cp',name+':/data/k92n/ci-backup.db',str(backup))
   anchor=hashlib.sha256(backup.read_bytes()).hexdigest()
   check('backup transported outside source container',backup.is_file() and backup.stat().st_size>0)
   bad=transfer/'corrupt.db';bad.write_bytes(b'BROKEN!'+backup.read_bytes()[7:])
   rejected=transfer/'rejected.db'
   r=subprocess.run([os.sys.executable,str(ROOT/'tools/backup.py'),'restore-new',str(bad),str(rejected)],capture_output=True,text=True,timeout=30)
   check('corrupt off-container backup cannot be restored',r.returncode!=0 and not rejected.exists())
   check('failed restore does not affect running source ledger',req('/api/integrity')[1]==golden and req('/api/customers/7/balances?accountId=1')[1]==golden_balances)
   clean=transfer/'clean';clean.mkdir();restored=clean/'k92n-local.db'
   r=subprocess.run([os.sys.executable,str(ROOT/'tools/backup.py'),'restore-new',str(backup),str(restored),'--expected-sha256',anchor],capture_output=True,text=True,timeout=30)
   check('off-container clean restore succeeds',r.returncode==0 and restored.is_file())
   docker('volume','create',restored_volume)
   # One-off preparation owns only disposable CI paths. It is not a Render disk fix.
   docker('run','--rm','--user','0','--entrypoint','bash','-v',str(clean.resolve())+':/restore-input:ro','-v',restored_volume+':/data',image,'-c','mkdir -p /data/k92n && cp /restore-input/k92n-local.db /data/k92n/k92n-local.db && chown -R app:app /data && chmod 700 /data /data/k92n')
   docker('rm','-f',name);volume=restored_volume;start()
   result=req('/api/integrity?expectedHead='+golden['headHash'])[1]
   check('restored container count and external HeadHash match',result['isValid'] and result['entriesChecked']==golden['entriesChecked'] and result['headHash']==golden['headHash'])
   check('restored container customer balance matches',req('/api/customers/7/balances?accountId=1')[1]==golden_balances)
   sql="import sqlite3; c=sqlite3.connect('/data/k92n/k92n-local.db'); assert c.execute('PRAGMA integrity_check').fetchall()==[('ok',)]; assert c.execute('PRAGMA foreign_key_check').fetchall()==[]; print('SQLITE_RECOVERY_CHECKS_PASS')"
   check('restored container integrity_check and foreign_key_check',docker('exec',name,'python3','-c',sql).stdout.strip()=='SQLITE_RECOVERY_CHECKS_PASS')
   check('restore input checksum remains unchanged',hashlib.sha256(backup.read_bytes()).hexdigest()==anchor)
  logs=docker('logs',name);check('secret absent from container logs',token not in logs.stdout+logs.stderr)
 except Exception as e:failure=type(e).__name__+': '+str(e).replace(token,'[REDACTED]')
 finally:
  docker('rm','-f',name,ok=False)
  for v in [original_volume,restored_volume]:docker('volume','rm',v,ok=False)
 report={'scope':'real Docker, independent backup transport, clean restored volume; NOT Render verification','commit':os.environ.get('GITHUB_SHA'),'checks':checks,'failure':failure,'productionReady':False}
 (ROOT/'evidence').mkdir(exist_ok=True)
 (ROOT/'evidence/docker-ci-results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'checks':len(checks),'passed':sum(c['status']=='PASS' for c in checks),'failure':failure}))
 return 1 if failure else 0
if __name__=='__main__':raise SystemExit(main())
