import json,sys
from pathlib import Path
from jsonschema import Draft202012Validator
from scripts.verify_signatures import *
def check(ok,code):
 if not ok:raise ValueError(code)
def schema(b,p,x):
 check(Draft202012Validator(load(b,p)).is_valid(x),'ERR_SCHEMA')
def run_enforcement(b):
 try:
  p=load(b,'registry/products.json');s=load(b,'registry/services.json');g=load(b,'registry/platform_gate.json')
  for n,x in [('products',p),('services',s),('platform_gate',g)]:schema(b,'registry/'+n+'.schema.json',x)
  check(not any(m in json.dumps([p,s]).upper() for m in ['MOCK_SALE','SANDBOX_TX','FAKE_LICENSE','TEST_CHECKOUT']),'ERR_MOCK_DATA_LEAK')
  ids=[x['asset_id'] for x in p['products']]+[x['service_id'] for x in s['services']];check(len(ids)==len(set(ids)),'ERR_GLOBAL_ID_COLLISION')
  graph={x['asset_id']:x['dependencies']+([x['overlap_target']] if x['overlap_target'] else []) for x in p['products']}
  def dfs(n,stack):
   check(n in graph,'ERR_INVALID_REFERENCE');check(n not in stack,'ERR_CYCLE')
   for r in graph[n]:dfs(r,stack|{n})
  for n in graph:dfs(n,set())
  signed=False
  if g['platform_production_verified']:
   check(all(g[k] for k in ['attestation_report_path','attestation_key_id','attestation_signature_b64']),'ERR_PLATFORM_ATTESTATION_MISSING')
   r=load(b/'evidence/platform',g['attestation_report_path']);verify_ed25519_payload(b,g['attestation_key_id'],'platform_attestation',g['attestation_signature_b64'],r)
   for k in ['platform_version','environment','deployment_digest','platform_production_verified','payment_provider_verified','entitlement_pipeline_verified','delivery_pipeline_verified','mock_data_removed_verified']:check(k in r and type(r[k])==type(g[k]) and r[k]==g[k],'ERR_PLATFORM_CLAIM_MISMATCH')
   check(g['deployment_digest'] and g['delivery_pipeline_verified'] and g['mock_data_removed_verified'],'ERR_PLATFORM_GATE_INCOMPLETE');signed=True
  for x in p['products']:
   if x['release_gate']=='G3' or x['evidence_manifest_path']:
    check(x['evidence_manifest_path'],'ERR_EVIDENCE_MISSING');e=load(b/'evidence/products',x['evidence_manifest_path']);schema(b,'audit/evidence.schema.json',e)
    check(e['asset_id']==x['asset_id'] and e['asset_version']==x['version'],'ERR_VERSION_MISMATCH');v=e['verification'];check(v['source']['status']=='VERIFIED','ERR_SOURCE_UNVERIFIED');check(v['artifact']['status']=='VERIFIED','ERR_ARTIFACT_STATUS_UNVERIFIED')
    a=sha256_file(resolve_safe_file(b/'artifacts',v['artifact']['path']));check(a==v['artifact']['expected_sha256'],'ERR_ARTIFACT_SHA256_MISMATCH')
    try:f=resolve_safe_file(b/'evidence/runtime',v['runtime']['report_path'])
    except ValueError as ex:raise ValueError('ERR_RUNTIME_REPORT_MISSING: '+str(ex))
    h=sha256_file(f);check(h==v['runtime']['test_report_sha256'],'ERR_RUNTIME_REPORT_SHA256_MISMATCH');r=json.loads(f.read_text());schema(b,'audit/runtime_report.schema.json',r)
    check(v['runtime']['status']==r['status']=='PASSED' and r['tests_total']==r['tests_passed'] and r['asset_id']==x['asset_id'] and r['asset_version']==x['version'] and r['artifact_sha256']==a,'ERR_RUNTIME_BINDING_MISMATCH')
    check(all(v['commercial'].values()) and e['release_gate_approved'],'ERR_COMMERCIAL_UNAPPROVED');sig=v['signature'];verify_ed25519_payload(b,sig['trusted_key_id'],'product_release',sig['signature_b64'],dict(asset_id=x['asset_id'],asset_version=x['version'],source_commit_sha=v['source']['commit_sha'],artifact_sha256=a,runtime_report_sha256=h,commercial_approved=True))
   if x['commercial_sale_enabled']:
    check(x['pricing_tier'] in ['FREE','PAID'],'ERR_PRICING_UNDECIDED');check(signed,'ERR_PLATFORM_NOT_VERIFIED')
    if x['pricing_tier']=='PAID':check(g['payment_provider_verified'],'ERR_PAYMENT_GATE_BLOCKED')
    else:check(g['entitlement_pipeline_verified'],'ERR_ENTITLEMENT_GATE_BLOCKED')
  for x in s['services']:
   if x['booking_enabled']:
    check(x['evidence_manifest_path'],'ERR_SERVICE_EVIDENCE_MISSING');e=load(b/'evidence/services',x['evidence_manifest_path']);schema(b,'audit/service_evidence.schema.json',e);check(e['service_id']==x['service_id'] and e['scope_approved'] and e['sla_approved'],'ERR_SERVICE_UNAPPROVED');key=e.pop('trusted_key_id');sig=e.pop('signature_b64');verify_ed25519_payload(b,key,'service_approval',sig,e);check(signed,'ERR_SERVICE_BOOKING_BLOCKED')
  return True,[]
 except (ValueError,OSError,KeyError,TypeError) as e:return False,[str(e)]
if __name__=='__main__':
 ok,errs=run_enforcement(Path('.'));print(json.dumps(dict(status='ACCEPTED' if ok else 'REJECTED',errors=errs)));sys.exit(not ok)
