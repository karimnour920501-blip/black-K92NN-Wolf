#!/usr/bin/env bash
set -euo pipefail
: "${BLACKWOLF_ADMIN_TOKEN:?required}"
python3 - <<'PY'
import json, os, urllib.request, urllib.error, uuid
base = os.environ.get("BASE", "http://127.0.0.1:8080").rstrip("/")
token = os.environ["BLACKWOLF_ADMIN_TOKEN"]
def call(method, path, body=None, authorization=True):
    headers = {"Content-Type":"application/json"}
    if authorization: headers["X-Admin-Token"] = token
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base+path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        return e.code, None
assert call("GET", "/health", authorization=False)[0] == 200
assert call("GET", "/ready", authorization=False)[0] == 200
assert call("GET", "/api/projects", authorization=False)[0] == 401
assert call("GET", "/api/projects", authorization=True)[0] == 200
assert call("GET", "/api/projects", authorization=True)[1] is not None
assert call("GET", "/api/projects", authorization=True)[0] == 200
assert call("POST", "/api/projects", {"name":"bad"}, authorization=False)[0] == 401
assert call("POST", "/api/projects", {"name":"  "})[0] == 400
assert call("POST", "/api/projects", {"name":"x"*121})[0] == 400
name = "ci-smoke-" + uuid.uuid4().hex
status, created = call("POST", "/api/projects", {"name":name})
assert status == 201 and created["name"] == name and created["id"]
status, projects = call("GET", "/api/projects")
assert status == 200 and any(p["id"] == created["id"] for p in projects)
status, audit = call("GET", "/api/audit")
assert status == 200 and any(a["action"] == "project.created" and a["target"] == created["id"] for a in audit)
assert call("GET", "/api/servers")[0] == 200

# Tenant isolation tests: two independent credentials and no cross-tenant project leakage.
key_a = uuid.uuid4().hex + uuid.uuid4().hex
key_b = uuid.uuid4().hex + uuid.uuid4().hex
def tenant_call(method, path, key, body=None):
    headers = {"Content-Type":"application/json", "X-Tenant-Key":key}
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base+path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        return e.code, None
for label,key in [("A",key_a),("B",key_b)]:
    status, result = call("POST", "/admin/tenants", {"name":"ci-tenant-"+label, "apiKey":key})
    assert status == 201 and result["id"]
assert tenant_call("GET","/api/v1/tenant/projects","invalid")[0] == 401
assert tenant_call("GET","/api/v1/tenant/projects",key_a)[0] == 200
assert tenant_call("GET","/api/v1/tenant/projects",key_b)[0] == 200
status, project_a = tenant_call("POST","/api/v1/tenant/projects",key_a,{"name":"tenant-a-private"})
assert status == 201
status, projects_a = tenant_call("GET","/api/v1/tenant/projects",key_a)
assert status == 200 and any(p["id"] == project_a["id"] for p in projects_a)
status, projects_b = tenant_call("GET","/api/v1/tenant/projects",key_b)
assert status == 200 and all(p["id"] != project_a["id"] for p in projects_b)
assert tenant_call("POST","/api/v1/tenant/projects",key_b,{"name":" "})[0] == 400
print("TENANT_ISOLATION_PASS: scoped reads writes unauthorized and validation")

print("SMOKE_PASS: health ready auth validation create persistence audit servers tenants")
PY
