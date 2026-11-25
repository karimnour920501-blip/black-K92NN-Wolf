import json,base64,shutil,re
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from scripts.verify_signatures import canonical_json_bytes,sha256_file
from scripts.enforce_release_gates import run_enforcement
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def env(tmp_path):
 b=tmp_path/'repo';shutil.copytree(ROOT,b,ignore=shutil.ignore_patterns('tests','__pycache__','.pytest_cache'))
 def read(p):return json.loads((b/p).read_text())
 def write(p,x):(b/p).write_text(json.dumps(x))
 p=read('registry/products.json');p['products']=p['products'][:1];write('registry/products.json',p)
 keys={k:Ed25519PrivateKey.generate() for k in ['prod','plat','svc','revoked','rogue']}
 roles={'prod':'product_release','plat':'platform_attestation','svc':'service_approval','revoked':'product_release'}
 for k in roles:(b/f'trust/public_keys/{k}.pub').write_text(base64.b64encode(keys[k].public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode())
 write('trust/trusted_keys.json',{'keys':{k:dict(algorithm='Ed25519',public_key_file=k+'.pub',roles=[r]) for k,r in roles.items()}});write('trust/revoked_keys.json',{'revoked_key_ids':['revoked']})
 def sign(k,p):return base64.b64encode(keys[k].sign(canonical_json_bytes(p))).decode()
 def product(**kw):
  p=read('registry/products.json');p['products'][0].update(kw);write('registry/products.json',p)
 def gate(payment=True,entitlement=True):
  g=read('registry/platform_gate.json');g.update(deployment_digest='b'*64,platform_production_verified=True,payment_provider_verified=payment,entitlement_pipeline_verified=entitlement,delivery_pipeline_verified=True,mock_data_removed_verified=True)
  r={k:v for k,v in g.items() if k!='gate_version' and not k.startswith('attestation_')};write('evidence/platform/p.json',r);g.update(attestation_report_path='p.json',attestation_key_id='plat',attestation_signature_b64=sign('plat',r));write('registry/platform_gate.json',g)
 def g3(sale=False,tier='PAID',key='prod',kid='prod',rv='1.0.1',passed=32,bad=False,source='VERIFIED',artifact='VERIFIED'):
  f=b/'artifacts/a.zip';f.write_bytes(b'fixture only');a=sha256_file(f);r=dict(asset_id='BW-001',asset_version=rv,artifact_sha256=a,environment='test',tests_total=32,tests_passed=passed,status='PASSED');write('evidence/runtime/r.json',r);h=sha256_file(b/'evidence/runtime/r.json');payload=dict(asset_id='BW-001',asset_version='1.0.1',source_commit_sha='a'*40,artifact_sha256=a,runtime_report_sha256=h,commercial_approved=True)
  e=dict(manifest_version='1.0.1',asset_id='BW-001',asset_version='1.0.1',verified_at='fixture',release_gate_approved=True,verification=dict(source=dict(repository='fixture',commit_sha='a'*40,status=source),artifact=dict(path='a.zip',expected_sha256='0'*64 if bad else a,status=artifact),signature=dict(algorithm='Ed25519',trusted_key_id=kid,signature_b64=sign(key,payload)),runtime=dict(report_path='r.json',test_report_sha256=h,status='PASSED'),commercial=dict(license_approved=True,documentation_verified=True,release_approved=True)));write('evidence/products/e.json',e);product(version='1.0.1',release_gate='G3',pricing_tier=tier,commercial_sale_enabled=sale,evidence_manifest_path='e.json')
 def mutate(section,field,value):
  e=read('evidence/products/e.json');e['verification'][section][field]=value;write('evidence/products/e.json',e)
 return b,read,write,product,gate,g3,mutate
CASES=[(1,'ERR_SCHEMA'),(2,'ERR_GLOBAL_ID_COLLISION'),(3,'ERR_INVALID_REFERENCE'),(4,'ERR_CYCLE'),(5,'ERR_SCHEMA'),(6,'ERR_EVIDENCE_MISSING'),(7,'ERR_ARTIFACT_SHA256_MISMATCH'),(8,'ERR_INVALID_SIGNATURE'),(9,'ERR_RUNTIME_BINDING_MISMATCH'),(10,'ERR_SERVICE_EVIDENCE_MISSING'),(11,'ERR_PLATFORM_NOT_VERIFIED'),(12,None),(13,'ERR_KEY_REVOKED'),(14,'ERR_KEY_UNTRUSTED'),(15,'ERR_KEY_ROLE_UNAUTHORIZED'),(16,'ERR_INVALID_SIGNATURE'),(17,'ERR_INVALID_SIGNATURE'),(18,'ERR_PATH_TRAVERSAL'),(19,'ERR_PATH_TRAVERSAL'),(20,'ERR_SYMLINK_ESCAPE'),(21,'ERR_NOT_REGULAR_FILE'),(22,'ERR_PLATFORM_CLAIM_MISMATCH'),(23,'ERR_PAYMENT_GATE_BLOCKED'),(24,'ERR_ENTITLEMENT_GATE_BLOCKED'),(25,'ERR_GLOBAL_ID_COLLISION'),(26,'ERR_RUNTIME_REPORT_MISSING'),(27,'ERR_RUNTIME_BINDING_MISMATCH'),(28,'ERR_MOCK_DATA_LEAK'),(29,'ERR_ARTIFACT_SHA256_MISMATCH'),(30,None),(31,None),(32,None),(33,'ERR_SCHEMA'),(34,'ERR_SOURCE_UNVERIFIED'),(35,'ERR_ARTIFACT_STATUS_UNVERIFIED'),(36,'ERR_INVALID_SIGNATURE')]
@pytest.mark.parametrize('n,expected',CASES)
def test_security(env,n,expected):
 b,r,w,p,g,f,m=env
 if n==1:x=r('registry/products.json');x['unexpected']=True;w('registry/products.json',x)
 if n==2:x=r('registry/products.json');x['products']*=2;w('registry/products.json',x)
 if n==3:p(overlap_target='BW-999')
 if n==4:p(dependencies=['BW-001'])
 if n==5:p(commercial_sale_enabled=True)
 if n==6:p(release_gate='G3')
 if n==7:f(bad=True)
 if n==8:f(key='rogue')
 if n==9:f(rv='1.0.0')
 if n in [10,25]:x=r('registry/services.json');x['services'][0].update({'booking_enabled':True} if n==10 else {'service_id':'BW-001'});w('registry/services.json',x)
 if n==11:f(sale=True)
 if n==13:f(key='revoked',kid='revoked')
 if n==14:f(key='rogue',kid='unknown')
 if n==15:f(key='plat',kid='plat')
 if n==16:f();m('source','commit_sha','b'*40)
 if n==17:f();m('signature','signature_b64','!!!')
 if n==18:p(release_gate='G3',evidence_manifest_path='../../etc/passwd')
 if n==19:f();m('artifact','path','/etc/hosts')
 if n==20:f();(b/'secret').write_text('fixture');(b/'artifacts/escape').symlink_to(b/'secret');m('artifact','path','escape')
 if n==21:f();(b/'artifacts/sub').mkdir();m('artifact','path','sub')
 if n==22:g(False);x=r('registry/platform_gate.json');x['payment_provider_verified']=True;w('registry/platform_gate.json',x)
 if n==23:g(False);f(sale=True)
 if n==24:g(True,False);f(sale=True,tier='FREE')
 if n==26:f();(b/'evidence/runtime/r.json').unlink()
 if n==27:f(passed=31)
 if n==28:p(name='MOCK_SALE')
 if n==29:f(bad=True);p(release_gate='G2')
 if n==30:f()
 if n==31:g(True,False);f(sale=True)
 if n==32:g(False,True);f(sale=True,tier='FREE')
 if n==33:g();f(sale=True,tier='UNDECIDED')
 if n==34:f(source='NOT_VERIFIED')
 if n==35:f(artifact='NOT_VERIFIED')
 if n==36:f();m('signature','signature_b64',r('evidence/products/e.json')['verification']['signature']['signature_b64']+'$$$')
 ok,errs=run_enforcement(b)
 if expected:assert not ok and expected in {c for e in errs for c in re.findall(r'\bERR_[A-Z0-9_]+\b',e)},errs
 else:assert ok,errs
