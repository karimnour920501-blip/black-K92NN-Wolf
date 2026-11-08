#!/usr/bin/env python3
"""Fail-closed K92N pin policy, restored NuGet integrity/signatures, and advisory gate."""
import argparse,base64,datetime,hashlib,json,os,re,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1]

def verify_pins():
 pins=json.loads((ROOT/'infra/supply-chain-lock.json').read_text())
 docker=(ROOT/'infra/Dockerfile.render').read_text();workflow=(REPO/'.github/workflows/k92n-hosting-verify.yml').read_text()
 images=re.findall(r'^FROM\s+(\S+)',docker,re.M)
 expected=['mcr.microsoft.com/dotnet/sdk:'+pins['dotnet-sdk']['tag']+'@'+pins['dotnet-sdk']['digest'],'mcr.microsoft.com/dotnet/aspnet:'+pins['dotnet-aspnet']['tag']+'@'+pins['dotnet-aspnet']['digest']]
 if images!=expected or not all(re.search(r'@sha256:[0-9a-f]{64}$',i) for i in images):raise ValueError('Docker FROM references must exactly match digest lock')
 actions=re.findall(r'^\s*-?\s*uses:\s*(\S+)',workflow,re.M)
 expected_actions=['actions/'+key+'@'+pins[key]['sha'] for key in ['checkout','setup-dotnet','upload-artifact']]
 if actions!=expected_actions or not all(re.fullmatch(r'actions/[\w-]+@[0-9a-f]{40}',a) for a in actions):raise ValueError('Every K92N action must match a full commit SHA in the lock')
 props=ET.parse(ROOT/'Directory.Build.props')
 if props.findtext('.//RestoreLockedMode')!='true':raise ValueError('Locked NuGet restore must be enabled')
 config=ET.parse(ROOT/'NuGet.Config');sources=config.findall('./packageSources/add')
 if len(sources)!=1 or sources[0].get('value')!='https://api.nuget.org/v3/index.json' or config.find('./packageSources/clear') is None:raise ValueError('NuGet sources must be explicitly scoped to nuget.org')
 return {'images':images,'actions':actions,'lock_sha256':hashlib.sha256((ROOT/'infra/supply-chain-lock.json').read_bytes()).hexdigest()}

def locked_packages():
 result={}
 for name in ['src/K92N.Core','src/K92N.Host','tests/K92N.Tests']:
  lock=json.loads((ROOT/name/'packages.lock.json').read_text())
  if lock['version']!=1:raise ValueError('Unsupported NuGet lock schema')
  for framework,items in lock['dependencies'].items():
   for package,entry in items.items():
    if entry['type']=='Project':continue
    version=entry['resolved'];expected=entry['contentHash']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',package) or not re.fullmatch(r'[A-Za-z0-9_.+-]+',version):raise ValueError('Invalid package path in lock')
    if len(base64.b64decode(expected,validate=True))!=64:raise ValueError('Invalid locked contentHash')
    key=(package.lower(),version)
    if key in result and result[key]!=expected:raise ValueError('Conflicting package hashes between project locks')
    result[key]=expected
 if not result:raise ValueError('No locked packages found')
 return result

def verify_packages(cache,dotnet):
 results=[]
 for (name,version),expected in sorted(locked_packages().items()):
  folder=cache/name/version;nupkg=folder/(name+'.'+version+'.nupkg')
  metadata=json.loads((folder/'.nupkg.metadata').read_text())
  if metadata.get('contentHash')!=expected:raise ValueError('NuGet normalized content hash differs from lock: '+name)
  raw_hash=base64.b64encode(hashlib.sha512(nupkg.read_bytes()).digest()).decode()
  if raw_hash!=(folder/(nupkg.name+'.sha512')).read_text().strip():raise ValueError('Package archive SHA-512 mismatch: '+name)
  # Repository signatures cover the signed ZIP; lock contentHash is NuGet's normalized hash,
  # which intentionally differs from SHA-512 of a repository-signed nupkg.
  v=subprocess.run([dotnet,'nuget','verify','--all',str(nupkg),'--verbosity','quiet'],capture_output=True,text=True,timeout=120)
  if v.returncode:raise ValueError('NuGet signature validation failed: '+name+' '+v.stderr[:1000]+v.stdout[:1000])
  results.append({'id':name,'version':version,'contentHash':expected,'archiveSha512':raw_hash,'signature':'PASS'})
 return results

def verify_audit(path):
 audit=json.loads(path.read_text())
 if audit.get('version')!=1 or not audit.get('projects'):raise ValueError('Audit returned no verifiable project graph')
 errors=[x for x in audit.get('logs',[]) if str(x.get('level','')).lower() in ['error','warning']]
 if errors:raise ValueError('Audit emitted warnings/errors; cannot treat missing advisory data as PASS')
 count=0
 for project in audit['projects']:
  if not project.get('frameworks'):raise ValueError('Audit project contains no frameworks')
  for framework in project['frameworks']:
   for group in ['topLevelPackages','transitivePackages']:
    for package in framework.get(group,[]):count+=len(package.get('vulnerabilities',[]))
 if count:raise ValueError('NuGet reports '+str(count)+' known package vulnerabilities')
 return {'known_package_vulnerabilities_reported':count,'scope':'NuGet restored graph only; not an OS/runtime or full security audit'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--packages',type=Path);p.add_argument('--dotnet',default='dotnet');p.add_argument('--audit',type=Path);a=p.parse_args()
 report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':os.environ.get('GITHUB_SHA'),'production_ready':False}
 name='nuget-audit-gate.json' if a.audit else 'dependency-integrity-results.json' if a.packages else 'supply-chain-results.json'
 try:
  report['pins']=verify_pins()
  if a.packages:report['packages']=verify_packages(a.packages,a.dotnet)
  if a.audit:report['audit']=verify_audit(a.audit)
  report['status']='PASS'
 except Exception as e:report['status']='FAIL';report['error']=type(e).__name__+': '+str(e)
 (ROOT/'evidence').mkdir(exist_ok=True);(ROOT/'evidence'/name).write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'status':report['status'],'report':name,'error':report.get('error')}))
 return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
