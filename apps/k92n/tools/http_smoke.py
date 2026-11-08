#!/usr/bin/env python3
"""Real HTTP integration against the compiled ASP.NET host, with a disposable DB."""
import argparse,copy,datetime,hashlib,json,os,secrets,socket,subprocess,tempfile,time,urllib.error,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--dotnet',default='dotnet');parser.add_argument('--host-path');args=parser.parse_args()
 assembly=Path(args.host_path).resolve() if args.host_path else ROOT/'src/K92N.Host/bin/Release/net10.0/K92N.Host.dll'
 if not assembly.exists():raise SystemExit('Build Release host first')
 checks=[]
 with tempfile.TemporaryDirectory(prefix='k92n-http-') as td:
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  token=secrets.token_urlsafe(40);origin=f'http://127.0.0.1:{port}'
  env=os.environ.copy();env.update(K92N_OPERATOR_TOKEN=token,K92N_DATA_DIR=td,ASPNETCORE_URLS=origin,ASPNETCORE_ENVIRONMENT='Production',DOTNET_NOLOGO='1')
  logpath=ROOT/'evidence/http-host.log'
  with logpath.open('w') as logfile:
   command=[args.dotnet,str(assembly)] if assembly.suffix=='.dll' else [str(assembly)]
   process=subprocess.Popen(command,cwd=assembly.parent if args.host_path else ROOT/'src/K92N.Host',env=env,stdout=logfile,stderr=subprocess.STDOUT)
   def req(path,body=None,auth=True,raw=None):
    headers={'Authorization':'Bearer '+(token if auth is True else auth)} if auth else {}
    if body is not None or raw is not None:headers['Content-Type']='application/json'
    data=raw if raw is not None else json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(origin+path,data=data,headers=headers,method='POST' if data is not None else 'GET')
    try:
     with urllib.request.urlopen(r,timeout=10) as response:status=response.status;content=response.read();h=dict(response.headers)
    except urllib.error.HTTPError as e:status=e.code;content=e.read();h=dict(e.headers)
    try:parsed=json.loads(content)
    except (json.JSONDecodeError,UnicodeDecodeError):parsed=content.decode(errors='replace')
    return status,parsed,h
   def check(name,condition):
    checks.append({'name':name,'status':'PASS' if condition else 'FAIL'})
    if not condition:raise AssertionError(name)
   failure=None
   try:
    for _ in range(100):
     if process.poll() is not None:raise RuntimeError('Host exited before health check')
     try:
      if req('/healthz',auth=False)[0]==200:break
     except (urllib.error.URLError,ConnectionError):pass
     time.sleep(.1)
    else:raise RuntimeError('Host did not become ready')
    status,data,headers=req('/healthz',auth=False);check('healthz real host',status==200 and data['productionReady'] is False)
    check('unauthenticated rejected',req('/api/status',auth=False)[0]==401)
    check('wrong token rejected',req('/api/status',auth='incorrect')[0]==401)
    status,data,headers=req('/api/status');check('authenticated status',status==200 and data['productionReady'] is False)
    check('API responses not cached',headers.get('Cache-Control')=='no-store')
    status,data,headers=req('/',auth=False);check('Arabic HTML served',status==200 and 'K92N' in data and 'Content-Security-Policy' in headers)
    for id,code,name in [(1,'1000','Cash'),(2,'1200','Receivables')]:check('create account '+str(id),req('/api/accounts',{'id':id,'code':code,'name':name})[0]==201)
    check('duplicate account rejected',req('/api/accounts',{'id':1,'code':'OTHER','name':'duplicate'})[0]==422)
    entry={'entryDate':'2026-11-08','description':'HTTP test','currencyCode':'USD','reference':'HTTP-1','entryType':'ADJUSTMENT','createdBy':None,'idempotencyKey':'http-1','lines':[{'accountId':2,'currencyCode':'USD','debitOrig':10,'creditOrig':0,'debitBase':10,'creditBase':0,'customerId':7,'invoiceId':None},{'accountId':1,'currencyCode':'USD','debitOrig':0,'creditOrig':10,'debitBase':0,'creditBase':10,'customerId':None,'invoiceId':None}]}
    status,data,_=req('/api/journal_entries',entry);check('atomic HTTP posting',status==200 and data['id']>0);id=data['id']
    status,data,_=req('/api/journal_entries',entry);check('idempotent retry returns original ID',status==200 and data['id']==id)
    conflict=copy.deepcopy(entry);conflict['description']='changed';check('idempotency conflict',req('/api/journal_entries',conflict)[0]==409)
    for name,change in [('negative',lambda e:e['lines'][0].update(debitOrig=-1,debitBase=-1)),('precision',lambda e:e['lines'][0].update(debitOrig=10.001,debitBase=10.001)),('unbalanced',lambda e:e['lines'][0].update(debitOrig=11,debitBase=11)),('unknown account',lambda e:e['lines'][0].update(accountId=999)),('invalid date',lambda e:e.update(entryDate='2026-13-45'))]:
     e=copy.deepcopy(entry);e['idempotencyKey']='bad-'+name;change(e);check(name+' rejected',req('/api/journal_entries',e)[0] in [400,422])
    status,data,_=req('/api/integrity');check('rejected writes rolled back',status==200 and data['isValid'] and data['entriesChecked']==1)
    status,data,_=req('/api/customers/7/balances?accountId=2');check('customer control-account balance',status==200 and data=={'USD':1000})
    check('malformed JSON rejected',req('/api/journal_entries',raw=b'{broken')[0]==400)
    status,data,_=req(f'/api/journal_entries/{id}/reversal',{'date':'2026-11-09','reason':'HTTP correction','idempotencyKey':'rev-http-1'});check('HTTP reversal',status==200 and data['id']!=id)
    check('second reversal rejected',req(f'/api/journal_entries/{id}/reversal',{'date':'2026-11-09','reason':'duplicate','idempotencyKey':'rev-http-2'})[0]==422)
    status,data,_=req('/api/integrity');check('mirror integrity after reversal',status==200 and data['isValid'] and data['entriesChecked']==2)
    status,data,_=req('/api/customers/7/balances?accountId=2');check('reversal clears customer balance',status==200 and data=={'USD':0})
    status,data,_=req('/api/integrity?expectedHead='+'1'*64);check('external anchor mismatch reported',status==200 and not data['isValid'] and data['problem']=='EXTERNAL_ANCHOR_MISMATCH')
    e={'kind':'decision','entityId':'ADR-HTTP','payload':{'text':'recorded','status':'RECORDED'}};check('governance event recorded',req('/api/events',e)[0]==200)
    a=req('/api/replay');b=req('/api/replay');check('deterministic real replay',a[0]==200 and a[1]['isValid'] and a[1]==b[1])
    check('raw events exported',len(req('/api/events')[1])==1)
    e['entityId']='evidence-fake';e['payload']['status']='VERIFIED';check('submitted verification claim blocked',req('/api/events',e)[0]==422)
    check('period lock recorded',req('/api/period_locks',{'through':'2026-11-10'})[0]==200)
    e=copy.deepcopy(entry);e['idempotencyKey']='locked';check('locked period rejects posting',req('/api/journal_entries',e)[0]==422)
   except Exception as e:failure=type(e).__name__+': '+str(e)
   finally:
    process.terminate()
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
  log=logpath.read_text();check('operator token absent from logs',token not in log)
  report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Real compiled ASP.NET Core process + SQLite + HTTP; disposable database','host_path':str(assembly),'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/K92N.Core/Store.cs',ROOT/'src/K92N.Core/schema.sql',ROOT/'src/K92N.Host/Program.cs']},'artifact_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [assembly,assembly.parent/'K92N.Host.dll',assembly.parent/'K92N.Core.dll']},'checks':checks,'failure':failure,'production_ready':False}
  (ROOT/'evidence/http-results.json').write_text(json.dumps(report,indent=2))
  print(json.dumps({'checks':len(checks),'passed':sum(c['status']=='PASS' for c in checks),'failure':failure},indent=2))
  return 1 if failure or any(c['status']=='FAIL' for c in checks) else 0
if __name__=='__main__':raise SystemExit(main())
