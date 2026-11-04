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
print("SMOKE_PASS: health ready auth validation create persistence audit servers")
PY
