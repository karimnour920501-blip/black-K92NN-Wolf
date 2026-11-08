#!/usr/bin/env python3
"""Real HTTP pilot contract tests, with an isolated disposable ledger."""
import argparse,copy,datetime,json,os,subprocess,tempfile
from pathlib import Path
from recovery_ci import Host,digest
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--dotnet',default='dotnet');a=p.parse_args();checks=[];failure=None
 def check(name,value):
  checks.append({'name':name,'status':'PASS' if value else 'FAIL'})
  if not value:raise AssertionError(name)
 try:
  with tempfile.TemporaryDirectory(prefix='k92n-pilot-contract-') as td,Host(a.dotnet,ROOT/'src/K92N.Host/bin/Release/net10.0/K92N.Host.dll',Path(td)) as h:
   check('read accounts requires authentication',h.request('/api/accounts',auth=False)[0]==401)
   check('statement requires authentication',h.request('/api/customers/7/statement?accountId=2',auth=False)[0]==401)
   check('pilot posting requires authentication',h.request('/api/pilot/postings',{},auth=False)[0]==401)
   check('initial accounts empty',h.get('/api/accounts')==[])
   currencies=h.get('/api/currencies');check('currency precision supplied by server',any(c['code']=='USD' and c['minorUnits']==2 and c['isBase'] for c in currencies) and any(c['code']=='SYP' and c['minorUnits']==0 for c in currencies))
   for id in ['1','2']:
    check('create pilot account '+id,h.request('/api/pilot/accounts',{'id':id,'code':id,'name':'حساب '+id})[0]==201)
   check('account IDs serialized exactly as strings',h.get('/api/accounts')[1]['id']=='2')
   empty=h.get('/api/customers/7/statement?accountId=2');check('unknown customer has empty statement',empty['balances']=={} and empty['lines']==[] and empty['next'] is None)
   req={'customerId':'7','controlAccountId':'2','counterAccountId':'1','entryDate':'2026-11-08','kind':'DEBT','currencyCode':'USD','amount':'125.50','baseAmount':None,'description':'دين تجريبي','idempotencyKey':'pilot-1'}
   status,data=h.request('/api/pilot/postings',req);check('pilot debt posts exact decimal string',status==200 and isinstance(data['id'],str));first=data['id']
   check('pilot retry returns same entry',h.request('/api/pilot/postings',req)[1]['id']==first)
   different=copy.deepcopy(req);different['amount']='126.50';check('pilot key cannot change amount',h.request('/api/pilot/postings',different)[0]==409)
   pay=copy.deepcopy(req);pay.update(kind='PAYMENT',amount='25.50',idempotencyKey='pilot-pay');check('pilot payment posts',h.request('/api/pilot/postings',pay)[0]==200)
   stmt=h.get('/api/customers/7/statement?accountId=2');check('payment reduces exact customer balance',stmt['balances']=={'USD':'10000'})
   check('statement shows sealed debt and payment newest first',len(stmt['lines'])==2 and stmt['lines'][0]['entryType']=='PAYMENT' and stmt['lines'][1]['entryId']==first and stmt['lines'][1]['debitMinor']=='12550')
   first_page=h.get('/api/customers/7/statement?accountId=2&limit=1');cursor=first_page['next'];check('statement page has stable cursor',len(first_page['lines'])==1 and cursor is not None)
   next_page=h.get(f"/api/customers/7/statement?accountId=2&limit=1&beforeEntryId={cursor['entryId']}&beforeLineNo={cursor['lineNo']}");check('pagination has no overlap or missing prior row',next_page['lines'][0]['entryId']==first and next_page['next'] is None and next_page['balances']==first_page['balances'])
   foreign=copy.deepcopy(req);foreign.update(currencyCode='TRY',amount='100.00',baseAmount='3.25',idempotencyKey='pilot-try');check('foreign posting records original and base amounts',h.request('/api/pilot/postings',foreign)[0]==200)
   stmt=h.get('/api/customers/7/statement?accountId=2');check('currencies stay separate with exact integer strings',stmt['balances']=={'TRY':'10000','USD':'10000'} and stmt['lines'][0]['debitBaseMinor']=='325')
   for name,updates in [('precision',{'amount':'1.001'}),('negative',{'amount':'-1'}),('exponent',{'amount':'1e2'}),('zero',{'amount':'0'}),('invalid control',{'controlAccountId':'0'}),('identical accounts',{'counterAccountId':'2'}),('unknown currency',{'currencyCode':'ZZZ'}),('unknown account',{'counterAccountId':'999'}),('missing idempotency key',{'idempotencyKey':''}),('bad date',{'entryDate':'2026-13-45'})]:
    bad=copy.deepcopy(req);bad.update(idempotencyKey='bad-'+name);bad.update(updates);check('reject '+name,h.request('/api/pilot/postings',bad)[0] in [400,422])
   check('failed postings leave ledger unchanged',h.get('/api/integrity')['entriesChecked']==3)
   check('page bound enforced',h.request('/api/customers/7/statement?accountId=2&limit=101')[0]==422)
   check('partial cursor rejected',h.request('/api/customers/7/statement?accountId=2&beforeEntryId=1')[0]==422)
   reverse={'entryId':first,'date':'2026-11-09','reason':'تصحيح','idempotencyKey':'pilot-reverse'}
   status,rv=h.request('/api/pilot/reversals',reverse);check('pilot reversal creates string ID',status==200 and isinstance(rv['id'],str))
   check('pilot reversal retry is idempotent',h.request('/api/pilot/reversals',reverse)[1]['id']==rv['id'])
   stmt=h.get('/api/customers/7/statement?accountId=2');check('reversal preserves original and marks reversal link',any(r['entryId']==first and r['isReversed'] for r in stmt['lines']) and any(r['reversesEntryId']==first for r in stmt['lines']))
   check('reversal after partial payment displays credit balance honestly',stmt['balances']['USD']=='-2550')
   check('final ledger remains balanced and intact',h.get('/api/integrity')['isValid'])
   env=os.environ.copy();env['K92N_OPERATOR_TOKEN']=h.token
   output=Path(td)/'preflight.json';r=subprocess.run([os.sys.executable,str(ROOT/'tools/pilot_preflight.py'),h.origin,'--output',str(output)],env=env,capture_output=True,text=True,timeout=30)
   check('read-only operational preflight succeeds',r.returncode==0 and json.loads(output.read_text())['failure'] is None)
   # Values beyond JavaScript safe integer range must round-trip as strings.
   huge='9007199254740993';check('large account identifier accepted exactly',h.request('/api/pilot/accounts',{'id':huge,'code':'huge','name':'large id'})[0]==201 and any(x['id']==huge for x in h.get('/api/accounts')))
   large=copy.deepcopy(req);large.update(customerId=huge,controlAccountId=huge,amount='10000000000000.00',idempotencyKey='pilot-huge');check('maximum amount posts without JS float conversion',h.request('/api/pilot/postings',large)[0]==200)
   check('large customer ID and minor amount are exact',h.get(f'/api/customers/{huge}/statement?accountId={huge}')['balances']=={'USD':'1000000000000000'})
 except Exception as e:failure=type(e).__name__+': '+str(e)
 result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':os.environ.get('GITHUB_SHA'),'scope':'real compiled HTTP pilot; synthetic single-operator data','checks':checks,'failure':failure,'production_ready':False}
 (ROOT/'evidence/pilot-http-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks':len(checks),'passed':sum(c['status']=='PASS' for c in checks),'failure':failure},indent=2));return 1 if failure else 0
if __name__=='__main__':raise SystemExit(main())
