#!/usr/bin/env bash
set -euo pipefail
base="${1:-http://localhost:5080}"
python3 - "$base" <<'PY2'
import json,sys,time,urllib.request
base=sys.argv[1]
def request(path,payload=None):
 data=None if payload is None else json.dumps(payload).encode()
 req=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as resp:return json.load(resp)
for project in ('proxylogon-dfir','node-sample'):
 id=request('/jobs',{'project':project})['job_id']
 for _ in range(120):
  job=request('/jobs/'+id)
  if job['status'] in ('passed','failed'):break
  time.sleep(2)
 print(project,job)
 assert job['status']=='passed',job
 replay=request('/jobs/'+id+'/replay',{})['job_id']
 for _ in range(120):
  replay_job=request('/jobs/'+replay)
  if replay_job['status'] in ('passed','failed'):break
  time.sleep(2)
 print('replay',replay_job)
 assert replay_job['status']=='passed',replay_job
 assert replay_job['artifactSha256']==job['artifactSha256'], 'Replay output mismatch'
assert request('/ledger/verify')['valid']
print('ledger chain verified')
PY2
