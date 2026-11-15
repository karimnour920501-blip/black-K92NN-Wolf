#!/usr/bin/env python3
"""Live HTTP/JWT and tenant RLS integration against a running API."""
import base64, hashlib, hmac, json, os, time, urllib.error, urllib.request, uuid

BASE = os.environ.get("API_BASE", "http://127.0.0.1:5187")
KEY = os.environ["JWT_SIGNING_KEY"].encode()
ISSUER = os.environ["JWT_ISSUER"]
AUDIENCE = os.environ["JWT_AUDIENCE"]
A, B = str(uuid.uuid4()), str(uuid.uuid4())

def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

def token(tenant, role="operator", *, secret=KEY, exp=None):
    header = b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = b64(json.dumps({"iss": ISSUER, "aud": AUDIENCE, "sub": "ci-user", "tenant_id": tenant, "role": role, "exp": exp or int(time.time()) + 600}, separators=(",", ":")).encode())
    body = header + "." + payload
    return body + "." + b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())

def request(method, path, body=None, jwt=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if jwt is not None:
        headers["Authorization"] = "Bearer " + jwt
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode()

def check(name, actual, expected):
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}")
    print("PASS", name, actual, flush=True)

for i in range(40):
    try:
        if request("GET", "/health/ready")[0] == 200:
            break
    except (OSError, TimeoutError):
        pass
    time.sleep(1)
else:
    raise RuntimeError("API readiness did not become healthy")

check("anonymous projects denied", request("GET", "/api/v1/projects")[0], 401)
check("bad signature denied", request("GET", "/api/v1/projects", jwt=token(A, secret=b"invalid-key" * 4))[0], 401)
check("expired JWT denied", request("GET", "/api/v1/projects", jwt=token(A, exp=1))[0], 401)
check("viewer cannot create", request("POST", "/api/v1/projects", {"name": "not-allowed"}, token(A, "viewer"))[0], 403)
check("viewer cannot execute", request("POST", "/api/v1/execute", {"command": "/design-brief test"}, token(A, "viewer"))[0], 403)
check("invalid tenant denied", request("GET", "/api/v1/projects", jwt=token("invalid-tenant"))[0], 403)
check("tenant A creates", request("POST", "/api/v1/projects", {"name": "tenant-a-secret"}, token(A))[0], 201)
check("tenant B creates", request("POST", "/api/v1/projects", {"name": "tenant-b-secret"}, token(B))[0], 201)
status, rows = request("GET", "/api/v1/projects", jwt=token(A))
check("tenant A list status", status, 200)
assert len(rows) == 1 and rows[0]["name"] == "tenant-a-secret", rows
print("PASS tenant A cannot read B", flush=True)
status, rows = request("GET", "/api/v1/projects", jwt=token(B))
check("tenant B list status", status, 200)
assert len(rows) == 1 and rows[0]["name"] == "tenant-b-secret", rows
print("PASS tenant B cannot read A", flush=True)
check("unimplemented command rejected", request("POST", "/api/v1/execute", {"command": "/brand-system x"}, token(A))[0], 409)
check("implemented command executes", request("POST", "/api/v1/execute", {"command": "/design-brief build a SaaS"}, token(A))[0], 200)
print("LIVE_HTTP_SECURITY_TESTS_PASSED", flush=True)
