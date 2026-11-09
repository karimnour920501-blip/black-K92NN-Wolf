#!/usr/bin/env python3
"""Read-only pilot checks. Never posts transactions or creates remote resources."""
import argparse,datetime,json,os,urllib.parse,urllib.request,urllib.error

def main():
 p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--output',default='evidence/pilot-preflight-results.json');a=p.parse_args()
 u=urllib.parse.urlsplit(a.url);host=u.hostname
 if u.username or u.password or u.query or u.fragment or u.path not in ['', '/'] or u.scheme not in ['http','https'] or (u.scheme=='http' and host not in ['localhost','127.0.0.1','::1']):p.error('Use a clean HTTPS origin, or HTTP loopback only; never put a secret in the URL')
 token=os.environ.get('K92N_OPERATOR_TOKEN','')
 if len(token)<32:p.error('Set K92N_OPERATOR_TOKEN in the environment')
 checks=[];failure=None
 def check(n,c):
  checks.append({'name':n,'status':'PASS' if c else 'FAIL'})
  if not c:raise AssertionError(n)
 # Do not forward a bearer secret through redirects to another origin.
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args):return None
 opener=urllib.request.build_opener(NoRedirect)
 def get(path,auth=True):
  req=urllib.request.Request(a.url.rstrip('/')+path,headers={'Authorization':'Bearer '+token} if auth else {})
  try:
   with opener.open(req,timeout=15) as r:return r.status,r.read(),r.headers
  except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
 try:
  status,body,_=get('/healthz',False);check('health reachable',status==200);check('production gate remains false',json.loads(body)['productionReady'] is False)
  check('unauthenticated API rejected',get('/api/accounts',False)[0]==401)
  status,_,headers=get('/api/accounts');check('authenticated API reachable',status==200);check('API not cacheable',headers.get('Cache-Control')=='no-store')
  status,body,_=get('/api/integrity');check('ledger semantic integrity',status==200 and json.loads(body)['isValid'])
  status,body,_=get('/api/currencies');check('currency metadata available',status==200 and len(json.loads(body))>0)
 except Exception as e:failure=type(e).__name__+': '+str(e).replace(token,'[REDACTED]')
 report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'origin':a.url,'scope':'read-only HTTP checks; not disk restart/redeploy or phone acceptance','checks':checks,'failure':failure,'productionReady':False}
 from pathlib import Path
 output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'checks':len(checks),'passed':sum(c['status']=='PASS' for c in checks),'failure':failure}))
 return 1 if failure else 0
if __name__=='__main__':raise SystemExit(main())
