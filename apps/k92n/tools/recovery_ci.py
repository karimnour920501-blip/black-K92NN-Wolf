#!/usr/bin/env python3
"""Real compiled-host recovery drill. All data is synthetic and disposable."""
import argparse,contextlib,datetime,hashlib,json,os,secrets,shutil,socket,sqlite3,subprocess,tempfile,time,urllib.error,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Host:
 def __init__(self,dotnet,assembly,data):
  self.dotnet=dotnet;self.assembly=assembly;self.data=data;self.token=secrets.token_urlsafe(40)
 def __enter__(self):
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  self.origin=f'http://127.0.0.1:{port}';self.data.mkdir(parents=True,exist_ok=True)
  env=os.environ.copy();env.update(K92N_OPERATOR_TOKEN=self.token,K92N_DATA_DIR=str(self.data),ASPNETCORE_URLS=self.origin,ASPNETCORE_ENVIRONMENT='Production')
  self.log=tempfile.TemporaryFile(mode='w+t')
  self.process=subprocess.Popen([self.dotnet,str(self.assembly)],cwd=ROOT/'src/K92N.Host',env=env,stdout=self.log,stderr=subprocess.STDOUT)
  try:
   for _ in range(100):
    if self.process.poll() is not None:raise RuntimeError('Recovery host exited during startup')
    try:
     if self.request('/healthz',auth=False)[0]==200:return self
    except (urllib.error.URLError,ConnectionError,TimeoutError):pass
    time.sleep(.1)
   raise RuntimeError('Recovery host did not become ready')
  except BaseException:self.__exit__(None,None,None);raise
 def __exit__(self,*args):
  self.process.terminate()
  try:self.process.wait(timeout=10)
  except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
  self.log.seek(0);log=self.log.read();self.log.close()
  if self.token in log:raise AssertionError('Operator secret appeared in host log')
 def request(self,path,body=None,auth=True):
  headers={'Authorization':'Bearer '+self.token} if auth else {}
  data=None
  if body is not None:data=json.dumps(body).encode();headers['Content-Type']='application/json'
  try:
   with urllib.request.urlopen(urllib.request.Request(self.origin+path,data=data,headers=headers),timeout=10) as r:return r.status,json.loads(r.read())
  except urllib.error.HTTPError as e:return e.code,{}
 def get(self,path):
  status,result=self.request(path)
  if status!=200:raise AssertionError('API read rejected '+path)
  return result

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows_snapshot(path):
 with contextlib.closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  db.execute('BEGIN')
  names=[r[0] for r in db.execute("SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name")]
  rows={}
  for name in names:
   quoted='"'+name.replace('"','""')+'"';n=len(db.execute('PRAGMA table_info('+quoted+')').fetchall())
   rows[name]=db.execute('SELECT * FROM '+quoted+' ORDER BY '+','.join(str(i+1) for i in range(n))).fetchall()
  return rows

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--dotnet',default='dotnet');a=parser.parse_args()
 assembly=ROOT/'src/K92N.Host/bin/Release/net10.0/K92N.Host.dll'
 if not assembly.is_file():raise SystemExit('Build Release host before recovery drill')
 checks=[];failure=None;anchor=None;sql_hash=None
 def check(name,condition):
  checks.append({'name':name,'status':'PASS' if condition else 'FAIL'})
  if not condition:raise AssertionError(name)
 def copy_cli(op,source,dest,expected=None):
  args=[os.sys.executable,str(ROOT/'tools/backup.py'),op,str(source),str(dest)]
  if expected is not None:args+=['--expected-sha256',expected]
  return subprocess.run(args,capture_output=True,text=True,timeout=30)
 try:
  with tempfile.TemporaryDirectory(prefix='k92n-live-') as live_td,tempfile.TemporaryDirectory(prefix='k92n-offservice-') as transfer_td,tempfile.TemporaryDirectory(prefix='k92n-restored-') as restore_td:
   live=Path(live_td);outside=Path(transfer_td);clean=Path(restore_td);source=live/'k92n-local.db'
   with Host(a.dotnet,assembly,live) as host:
    for id in [1,2]:check('seed account '+str(id),host.request('/api/accounts',{'id':id,'code':str(id),'name':'Recovery synthetic'})[0]==201)
    def entry(currency,orig,base,customer,key):
     return {'entryDate':'2026-11-08','description':'Recovery drill '+key,'currencyCode':currency,'reference':key,'entryType':'ADJUSTMENT','createdBy':None,'idempotencyKey':key,'lines':[{'accountId':2,'currencyCode':currency,'debitOrig':orig,'creditOrig':0,'debitBase':base,'creditBase':0,'customerId':customer,'invoiceId':None},{'accountId':1,'currencyCode':currency,'debitOrig':0,'creditOrig':orig,'debitBase':0,'creditBase':base,'customerId':None,'invoiceId':None}]}
    requests=[entry('USD',125.50,125.50,7,'recover-usd'),entry('TRY',100,3.25,7,'recover-try'),entry('USD',9,9,8,'recover-reverse')]
    ids=[]
    for i,req in enumerate(requests):
     status,result=host.request('/api/journal_entries',req);check('seed journal '+str(i+1),status==200);ids.append(result['id'])
    check('seed reversal',host.request(f'/api/journal_entries/{ids[2]}/reversal',{'date':'2026-11-09','reason':'recovery fixture','idempotencyKey':'recover-reversal'})[0]==200)
    check('seed governance event',host.request('/api/events',{'kind':'decision','entityId':'ADR-RECOVERY','payload':{'text':'synthetic'}})[0]==200)
    check('seed period lock',host.request('/api/period_locks',{'through':'2026-10-31'})[0]==200)
    integrity=host.get('/api/integrity');balances={str(id):host.get(f'/api/customers/{id}/balances?accountId=2') for id in [7,8]}
    check('nontrivial original ledger',integrity['isValid'] and integrity['entriesChecked']==4 and balances['7']=={'TRY':10000,'USD':12550} and balances['8']=={'USD':0})
    original_rows=rows_snapshot(source);replay=host.get('/api/replay')
    sql_hash=hashlib.sha256(json.dumps(original_rows,sort_keys=True).encode()).hexdigest()
    anchor={'entriesChecked':integrity['entriesChecked'],'headHash':integrity['headHash'],'balances':balances,'rowsSha256':sql_hash,'replay':replay}
    # Anchor is stored separately, before transport. It is not taken from the restored DB.
    (outside/'expected-anchor.json').write_text(json.dumps(anchor,indent=2))
    backup=live/'backup.db';r=copy_cli('backup',source,backup);check('online SQLite backup while host is running',r.returncode==0)
    shipped=outside/'transport.db';shutil.copyfile(backup,shipped);expected_sha=digest(backup)
    check('independent transport SHA-256 matches',digest(shipped)==expected_sha and shipped.parent!=source.parent)
    (outside/'transport.sha256').write_text(expected_sha)
    check('transport contains database only, no WAL sidecars',not Path(str(shipped)+'-wal').exists() and not Path(str(shipped)+'-shm').exists())
    wal_input=outside/'wal-dependent.db';shutil.copyfile(shipped,wal_input)
    with contextlib.closing(sqlite3.connect(wal_input)) as pending:
     pending.execute('PRAGMA journal_mode=WAL');pending.execute('CREATE TABLE pending_wal_probe(id INTEGER)');pending.commit()
     target=clean/'live-wal-output.db';r=copy_cli('restore-new',wal_input,target,digest(wal_input))
     check('WAL-dependent input cannot masquerade as standalone backup',r.returncode!=0 and not target.exists() and 'standalone backup' in r.stderr)
    # Corruption must be rejected even without an expected checksum.
    bad=outside/'corrupt.db';bad.write_bytes(b'BROKEN!'+shipped.read_bytes()[7:])
    target=clean/'bad-output.db';r=copy_cli('restore-new',bad,target)
    check('corrupt backup rejected structurally',r.returncode!=0 and not target.exists())
    target=clean/'bad-sha-output.db';r=copy_cli('restore-new',bad,target,expected_sha)
    check('transport checksum mismatch rejected',r.returncode!=0 and not target.exists())
    # A structurally readable database with FK violations must also be rejected.
    fk=outside/'foreign-key-broken.db';shutil.copyfile(shipped,fk)
    with contextlib.closing(sqlite3.connect(fk)) as db,db:
     db.execute('DROP TRIGGER journal_lines_no_update');db.execute('UPDATE journal_lines SET account_id=99999 WHERE entry_id=1 AND line_no=1')
    target=clean/'bad-fk-output.db';r=copy_cli('restore-new',fk,target,digest(fk))
    check('foreign-key broken backup rejected',r.returncode!=0 and not target.exists())
    # Valid SQLite whose content changed must fail the separately held checksum.
    modified=outside/'modified.db';shutil.copyfile(shipped,modified)
    with contextlib.closing(sqlite3.connect(modified)) as db,db:
     db.execute('DROP TRIGGER journal_entries_no_update');db.execute("UPDATE journal_entries SET description='modified' WHERE id=1")
    target=clean/'modified-output.db';r=copy_cli('restore-new',modified,target,expected_sha)
    check('readable tampered transport rejected by external checksum',r.returncode!=0 and not target.exists())
    r=copy_cli('restore-new',shipped,source,expected_sha)
    check('existing live database cannot be overwritten',r.returncode!=0)
    r=copy_cli('restore-new',source,source)
    check('source cannot be restore destination',r.returncode!=0)
    check('failed restores preserve original records and schema rows',rows_snapshot(source)==original_rows)
    check('failed restores preserve original balances and HeadHash',host.get('/api/integrity')==integrity and all(host.get(f'/api/customers/{id}/balances?accountId=2')==balances[str(id)] for id in [7,8]))
    check('failed restores leave no temporary output files',not list(clean.glob('.k92n-backup-*')))
   # Original is removed: successful restore must not accidentally depend on it or its WAL.
   shutil.rmtree(live)
   restored=clean/'k92n-local.db';r=copy_cli('restore-new',shipped,restored,expected_sha)
   check('clean restore succeeds with original removed',r.returncode==0 and restored.is_file())
   check('restored complete rows equal original',rows_snapshot(restored)==original_rows)
   with contextlib.closing(sqlite3.connect(restored)) as db:
    check('restored PRAGMA integrity_check',db.execute('PRAGMA integrity_check').fetchall()==[('ok',)])
    check('restored PRAGMA foreign_key_check',db.execute('PRAGMA foreign_key_check').fetchall()==[])
   with Host(a.dotnet,assembly,clean) as host:
    restored_report=host.get('/api/integrity?expectedHead='+anchor['headHash'])
    check('restored API integrity and external HeadHash',restored_report['isValid'] and restored_report['headHash']==anchor['headHash'])
    check('restored entry count matches original',restored_report['entriesChecked']==anchor['entriesChecked'])
    check('restored customer balances match original',all(host.get(f'/api/customers/{id}/balances?accountId=2')==anchor['balances'][str(id)] for id in [7,8]))
    check('restored governance replay matches original',host.get('/api/replay')==anchor['replay'])
    status,result=host.request('/api/journal_entries',requests[0]);check('restored idempotency returns original entry',status==200 and result['id']==ids[0] and host.get('/api/integrity')['entriesChecked']==4)
    wrong=host.get('/api/integrity?expectedHead='+'1'*64);check('restored API rejects wrong external anchor',not wrong['isValid'] and wrong['problem']=='EXTERNAL_ANCHOR_MISMATCH')
    check('restored rows unchanged by verification and retry',rows_snapshot(restored)==original_rows)
   check('restore input remains unchanged',digest(shipped)==expected_sha)
 except Exception as e:failure=type(e).__name__+': '+str(e)
 report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':os.environ.get('GITHUB_SHA'),'scope':'compiled ASP.NET + SQLite backup, independent directory transport, clean restore, real HTTP; synthetic data only','checks':checks,'failure':failure,'external_anchor':anchor,'source_hashes':{str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'tools/backup.py',Path(__file__),ROOT/'src/K92N.Core/Store.cs',ROOT/'src/K92N.Core/schema.sql',ROOT/'src/K92N.Host/Program.cs']},'production_ready':False}
 (ROOT/'evidence').mkdir(exist_ok=True);(ROOT/'evidence/recovery-ci-results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'checks':len(checks),'passed':sum(c['status']=='PASS' for c in checks),'failure':failure},indent=2))
 return 1 if failure else 0
if __name__=='__main__':raise SystemExit(main())
