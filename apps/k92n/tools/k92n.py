#!/usr/bin/env python3
"""Bounded, offline project tooling. Never executes arbitrary user shell commands."""
import argparse,datetime,hashlib,json,os,platform,shutil,sqlite3,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');temp.replace(path)
def files():
 for p in sorted(ROOT.rglob('*')):
  rel=p.relative_to(ROOT)
  if p.is_file() and not any(x in {'.runtime','bin','obj','__pycache__','.git'} for x in rel.parts) and str(rel)!='registry/package-manifest.json':yield p

def manifest():
 entries=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files()]
 write(ROOT/'registry/package-manifest.json',{'version':1,'files':entries});print(json.dumps({'files':len(entries),'manifest':'registry/package-manifest.json'}))
def verify():
 m=json.loads((ROOT/'registry/package-manifest.json').read_text());expected={r['path']:r for r in m['files']};actual={p.relative_to(ROOT).as_posix():p for p in files()};problems=[]
 for name,r in expected.items():
  p=(ROOT/name).resolve()
  if not p.is_relative_to(ROOT):problems.append('unsafe path '+name)
  elif name not in actual or sha(p)!=r['sha256']:problems.append('missing/modified '+name)
 problems.extend('unexpected '+p for p in actual.keys()-expected.keys())
 print(json.dumps({'valid':not problems,'files':len(expected),'problems':problems},indent=2));return int(bool(problems))
def index_docs():
 write(ROOT/'registry/documents.json',[{'id':'DOC-'+str(i+1).zfill(3),'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'status':'SAVED'} for i,p in enumerate(sorted(ROOT.rglob('*.md'))) if 'archive' not in p.relative_to(ROOT).parts]);print('registry/documents.json written')
def check(group):
 commands={'sql':[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'],'dotnet-build':['dotnet','build','src/K92N.Host/K92N.Host.csproj','-c','Release'],'dotnet-tests':['dotnet','run','--project','tests/K92N.Tests/K92N.Tests.csproj','-c','Release']}
 keys=list(commands) if group=='all' else [group];runs=[]
 for key in keys:
  cmd=commands[key];row={'id':key,'command':cmd,'cwd':str(ROOT),'at':stamp(),'schema_sha256':sha(ROOT/'src/K92N.Core/schema.sql'),'core_sha256':sha(ROOT/'src/K92N.Core/Store.cs')}
  if shutil.which(cmd[0]) is None:row.update(status='NOT_RUN',reason='Required executable not installed',exit_code=None)
  else:
   try:
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=120)
    log=ROOT/'evidence'/f'{key}.log';log.write_text(p.stdout+p.stderr)
    row.update(status='PASS' if p.returncode==0 else 'FAIL',exit_code=p.returncode,log=log.relative_to(ROOT).as_posix(),log_sha256=sha(log))
   except subprocess.TimeoutExpired:row.update(status='FAIL',reason='120 second timeout',exit_code=None)
  runs.append(row);print(key,row['status'])
 write(ROOT/'evidence/RESULTS.json',{'version':'1.0.1-local-verified','at':stamp(),'production_ready':False,'environment':{'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'platform':platform.platform()},'runs':runs,'not_verified':['Docker','browser on phone','migration from old ledger','OIDC/RBAC/RLS','backup and disaster recovery on target device']})
 return 1 if any(r['status']=='FAIL' for r in runs) else 2 if any(r['status']=='NOT_RUN' for r in runs) else 0

def canon(fields):
 data=b''
 for f in fields:
  if f is None:data+=b'-1:'
  else:
   s=str(f).encode('utf-8');data+=str(len(s)).encode('ascii')+b':'+s
 return hashlib.sha256(data).hexdigest()
def replay(events):
 head='0'*64;projection={}
 for seq,e in enumerate(events,1):
  if e['seq']!=seq or e['prevHash']!=head or e['hash']!=canon([2,seq,e['at'],e['kind'],e['entityId'],e['payload'],head]):raise ValueError('Invalid event chain at '+str(seq))
  projection[e['kind']+':'+e['entityId']]=json.loads(e['payload']);head=e['hash']
 return {'eventsChecked':len(events),'headHash':head,'projection':dict(sorted(projection.items()))}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['inspect','doc-index','manifest','verify-package','check','replay']);parser.add_argument('argument',nargs='?');a=parser.parse_args()
 if a.command=='inspect':print(json.dumps({'root':str(ROOT),'sources':json.loads((ROOT/'registry/sources.json').read_text()),'production_ready':False},ensure_ascii=False,indent=2))
 elif a.command=='doc-index':index_docs()
 elif a.command=='manifest':manifest()
 elif a.command=='verify-package':return verify()
 elif a.command=='check':
  if a.argument not in {None,'all','sql','dotnet-build','dotnet-tests'}:parser.error('Unknown check group')
  return check(a.argument or 'all')
 elif a.command=='replay':
  if not a.argument:parser.error('JSON file required')
  p=Path(a.argument)
  if p.stat().st_size>10_000_000:parser.error('Replay input exceeds 10 MB')
  print(json.dumps(replay(json.loads(p.read_text())),ensure_ascii=False,indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())
