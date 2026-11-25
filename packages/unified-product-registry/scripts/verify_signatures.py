import base64,hashlib,json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
def canonical_json_bytes(p):return json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha256_file(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def resolve_safe_file(root,rel):
 if not rel or not isinstance(rel,str):raise ValueError('ERR_PATH_EMPTY')
 root=root.resolve(strict=True);p=Path(rel)
 if p.is_absolute() or '..' in p.parts:raise ValueError('ERR_PATH_TRAVERSAL')
 p=(root/p).resolve()
 if not p.is_relative_to(root):raise ValueError('ERR_SYMLINK_ESCAPE')
 if not p.exists():raise ValueError('ERR_FILE_MISSING')
 if not p.is_file():raise ValueError('ERR_NOT_REGULAR_FILE')
 return p
def load(root,rel):return json.loads(resolve_safe_file(root,rel).read_text())
def verify_ed25519_payload(base,key,role,sig,payload):
 t=base/'trust';e=load(t,'trusted_keys.json')['keys'].get(key)
 if key in load(t,'revoked_keys.json')['revoked_key_ids']:raise ValueError('ERR_KEY_REVOKED')
 if not e or e['algorithm']!='Ed25519':raise ValueError('ERR_KEY_UNTRUSTED')
 if role not in e['roles']:raise ValueError('ERR_KEY_ROLE_UNAUTHORIZED')
 try:
  pub=base64.b64decode(resolve_safe_file(t/'public_keys',e['public_key_file']).read_text().strip(),validate=True)
  if len(pub)!=32:raise ValueError()
 except ValueError:raise ValueError('ERR_KEY_MALFORMED')
 try:
  sig=base64.b64decode(sig,validate=True)
  if len(sig)!=64:raise ValueError()
  Ed25519PublicKey.from_public_bytes(pub).verify(sig,canonical_json_bytes(payload))
 except (ValueError,TypeError,InvalidSignature):raise ValueError('ERR_INVALID_SIGNATURE')
