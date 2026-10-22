#!/usr/bin/env python3
"""WOLF DEPLOY Runtime Core: local static-site deployment MVP.

This is a real single-node runtime, not a cloud/Kubernetes deployer. It safely
validates and publishes static sites from WOLF_PROJECTS_ROOT using SQLite,
durable jobs, worker leases, hash-chained audit events, and idempotency keys.
It never executes project code or arbitrary shell commands.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

BASE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("WOLF_PROJECTS_ROOT", BASE / "projects")).resolve()
PUBLISHED = Path(os.environ.get("WOLF_PUBLISHED_ROOT", BASE / "data" / "published")).resolve()
DB_PATH = Path(os.environ.get("WOLF_DB_PATH", BASE / "data" / "runtime.sqlite3")).resolve()
HOST = os.environ.get("WOLF_HOST", "127.0.0.1")
PORT = int(os.environ.get("WOLF_PORT", "8088"))
MAX_FILES = int(os.environ.get("WOLF_MAX_FILES", "1000"))
MAX_BYTES = int(os.environ.get("WOLF_MAX_BYTES", str(100 * 1024 * 1024)))
LEASE_SECONDS = int(os.environ.get("WOLF_LEASE_SECONDS", "30"))
WORKER_ID = f"worker-{uuid.uuid4().hex[:10]}"
STOP = threading.Event()
DB_LOCK = threading.RLock()
TERMINAL = {"running", "failed", "cancelled"}
TRANSITIONS = {
    "queued": {"building", "cancelled"},
    "building": {"deploying", "failed", "queued", "cancelled"},
    "deploying": {"running", "failed", "queued", "cancelled"},
    "running": set(), "failed": {"queued"}, "cancelled": set(),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=10000")
    return con


def init_db() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    PUBLISHED.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
          request_hash TEXT NOT NULL, source_path TEXT NOT NULL,
          status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
          max_attempts INTEGER NOT NULL DEFAULT 3, lease_owner TEXT,
          lease_expires REAL, heartbeat_at TEXT, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, error TEXT, published_path TEXT,
          preview_path TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status,created_at);
        CREATE TABLE IF NOT EXISTS events(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(id),
          event_type TEXT NOT NULL, from_status TEXT, to_status TEXT,
          detail TEXT NOT NULL, created_at TEXT NOT NULL,
          prev_hash TEXT NOT NULL, hash TEXT NOT NULL
        );
        """)


def job_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item.pop("request_hash", None)
    item.pop("lease_owner", None)
    item.pop("lease_expires", None)
    return item


def add_event(db: sqlite3.Connection, job_id: str, kind: str,
              old: str | None, new: str | None, detail: dict) -> None:
    prior = db.execute("SELECT hash FROM events WHERE job_id=? ORDER BY seq DESC LIMIT 1", (job_id,)).fetchone()
    prev = prior["hash"] if prior else "GENESIS"
    created = now()
    payload = json.dumps({"job_id": job_id, "type": kind, "from": old, "to": new,
                          "detail": detail, "created_at": created}, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256((prev + "|" + payload).encode()).hexdigest()
    db.execute("INSERT INTO events(job_id,event_type,from_status,to_status,detail,created_at,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?)",
               (job_id, kind, old, new, json.dumps(detail, sort_keys=True), created, prev, digest))


def transition(db: sqlite3.Connection, job_id: str, new: str, detail: dict | None = None) -> None:
    row = db.execute("SELECT status,lease_owner,lease_expires FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise KeyError(job_id)
    old = row["status"]
    if new not in TRANSITIONS.get(old, set()):
        raise ValueError(f"invalid transition: {old} -> {new}")
    clear_lease = new in {"queued", "running", "failed", "cancelled"}
    db.execute("UPDATE jobs SET status=?,updated_at=?,error=?,lease_owner=?,lease_expires=? WHERE id=?",
               (new, now(), (detail or {}).get("error"), None if clear_lease else row["lease_owner"],
                None if clear_lease else row["lease_expires"], job_id))
    add_event(db, job_id, "state_transition", old, new, detail or {})


def create_job(source: str, key: str) -> tuple[dict, bool]:
    if not key or len(key) > 200:
        raise ValueError("Idempotency-Key header is required (max 200 chars)")
    candidate = (ROOT / source).resolve()
    try:
        relative = candidate.relative_to(ROOT)
    except ValueError:
        raise ValueError("source_dir must resolve inside WOLF_PROJECTS_ROOT")
    if not relative.parts or not candidate.is_dir():
        raise ValueError("source_dir must name an existing project folder inside projects/")
    canonical_source = relative.as_posix()
    req_hash = hashlib.sha256(canonical_source.encode()).hexdigest()
    with DB_LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT * FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
        if existing:
            if existing["request_hash"] != req_hash:
                db.rollback()
                raise Conflict("Idempotency-Key was already used with a different request")
            db.commit()
            return job_dict(existing), True
        jid, stamp = str(uuid.uuid4()), now()
        db.execute("INSERT INTO jobs(id,idempotency_key,request_hash,source_path,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                   (jid, key, req_hash, canonical_source, "queued", stamp, stamp))
        add_event(db, jid, "job_created", None, "queued", {"source_dir": canonical_source})
        db.commit()
        return job_dict(db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()), False


class Conflict(Exception):
    pass


def claim_job() -> dict | None:
    with DB_LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM jobs WHERE status='queued' AND attempt<max_attempts ORDER BY created_at,id LIMIT 1").fetchone()
        if not row:
            db.commit()
            return None
        jid, stamp = row["id"], now()
        db.execute("UPDATE jobs SET status='building',attempt=attempt+1,lease_owner=?,lease_expires=?,heartbeat_at=?,updated_at=? WHERE id=? AND status='queued'",
                   (WORKER_ID, time.time()+LEASE_SECONDS, stamp, stamp, jid))
        add_event(db, jid, "job_claimed", "queued", "building", {"worker_id": WORKER_ID, "attempt": row["attempt"]+1})
        claimed = db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        db.commit()
        return dict(claimed)


def heartbeat(job_id: str) -> None:
    with connect() as db:
        db.execute("UPDATE jobs SET lease_expires=?,heartbeat_at=?,updated_at=? WHERE id=? AND lease_owner=?",
                   (time.time()+LEASE_SECONDS, now(), now(), job_id, WORKER_ID))


def validate_static_site(source: Path) -> tuple[list[Path], int]:
    index = source / "index.html"
    if not index.is_file() or index.is_symlink():
        raise ValueError("static site must contain a regular index.html")
    files: list[Path] = []
    total = 0
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symbolic links are not allowed: {path.relative_to(source)}")
        if any(part.startswith(".") for part in path.relative_to(source).parts):
            raise ValueError(f"hidden files and directories are not publishable: {path.relative_to(source)}")
        if path.is_file():
            files.append(path)
            total += path.stat().st_size
            if len(files) > MAX_FILES:
                raise ValueError(f"site exceeds file limit ({MAX_FILES})")
            if total > MAX_BYTES:
                raise ValueError(f"site exceeds byte limit ({MAX_BYTES})")
    return files, total


def run_job(job: dict) -> None:
    jid = job["id"]
    source = (ROOT / job["source_path"]).resolve()
    target = (PUBLISHED / jid).resolve()
    try:
        files, total = validate_static_site(source)
        heartbeat(jid)
        with DB_LOCK, connect() as db:
            transition(db, jid, "deploying", {"validated_files": len(files), "bytes": total})
        temp = PUBLISHED / ("." + jid + ".tmp")
        if temp.exists():
            shutil.rmtree(temp)
        shutil.copytree(source, temp, symlinks=True)
        # Recheck copied content before atomically making it visible.
        copied_files, copied_bytes = validate_static_site(temp)
        if len(copied_files) != len(files) or copied_bytes != total:
            raise RuntimeError("artifact changed during copy; refusing publication")
        if target.exists():
            shutil.rmtree(target)
        os.replace(temp, target)
        with DB_LOCK, connect() as db:
            db.execute("UPDATE jobs SET published_path=?,preview_path=?,updated_at=? WHERE id=? AND lease_owner=?",
                       (str(target), f"/preview/{jid}/", now(), jid, WORKER_ID))
            transition(db, jid, "running", {"published_files": len(files), "bytes": total,
                                              "preview_path": f"/preview/{jid}/", "provider": "local-static"})
    except Exception as exc:
        with DB_LOCK, connect() as db:
            row = db.execute("SELECT status,lease_owner FROM jobs WHERE id=?", (jid,)).fetchone()
            if row and row["lease_owner"] == WORKER_ID and row["status"] in {"building", "deploying"}:
                transition(db, jid, "failed", {"error": str(exc)[:1000]})
        temp = PUBLISHED / ("." + jid + ".tmp")
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)


def reconcile() -> int:
    recovered = 0
    with DB_LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        expired = db.execute("SELECT id,status,attempt,max_attempts FROM jobs WHERE status IN ('building','deploying') AND lease_expires<?", (time.time(),)).fetchall()
        for row in expired:
            next_status = "queued" if row["attempt"] < row["max_attempts"] else "failed"
            transition(db, row["id"], next_status, {"reason": "worker lease expired", "attempt": row["attempt"]})
            recovered += 1
        db.commit()
    return recovered


def worker_loop() -> None:
    while not STOP.is_set():
        try:
            reconcile()
            job = claim_job()
            if job:
                run_job(job)
            else:
                STOP.wait(0.5)
        except Exception as exc:
            print(json.dumps({"level": "error", "component": "worker", "error": str(exc)}), flush=True)
            STOP.wait(1)


def safe_preview_file(job_id: str, raw_path: str) -> Path | None:
    if not job_id or any(not (char.isalnum() or char == "-") for char in job_id):
        return None
    base = (PUBLISHED / job_id).resolve()
    requested = PurePosixPath(unquote(raw_path).lstrip("/"))
    if any(part in {"..", "."} for part in requested.parts):
        return None
    try:
        path = (base.joinpath(*requested.parts) if requested.parts else base / "index.html").resolve()
        path.relative_to(base)
    except ValueError:
        return None
    if path.is_file() and not path.is_symlink():
        return path
    if path.is_dir() and (path / "index.html").is_file():
        return path / "index.html"
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "WolfDeployRuntime/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(json.dumps({"level": "info", "component": "http", "message": fmt % args}), flush=True)

    def send_json(self, status: int, body: dict | list) -> None:
        raw = json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def body_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > 32_768:
            raise ValueError("request body must be 1..32768 bytes")
        body = json.loads(self.rfile.read(length))
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        return body

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            raw = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'")
            self.end_headers()
            return self.wfile.write(raw)
        if parsed.path == "/api/health":
            try:
                with connect() as db:
                    db.execute("SELECT 1")
                    counts = {row["status"]: row["n"] for row in db.execute("SELECT status,count(*) n FROM jobs GROUP BY status")}
                return self.send_json(200, {"status": "ok", "runtime": "single-node", "database": "sqlite-wal", "worker": WORKER_ID, "jobs": counts})
            except Exception as exc:
                return self.send_json(503, {"status": "degraded", "error": str(exc)})
        if parsed.path == "/api/jobs":
            with connect() as db:
                rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100").fetchall()
            return self.send_json(200, [job_dict(r) for r in rows])
        if parsed.path.startswith("/api/jobs/"):
            parts = parsed.path.strip("/").split("/")
            jid = parts[2] if len(parts) >= 3 else ""
            with connect() as db:
                row = db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
                if not row:
                    return self.send_json(404, {"error": "job not found"})
                if len(parts) == 4 and parts[3] == "events":
                    events = db.execute("SELECT seq,event_type,from_status,to_status,detail,created_at,prev_hash,hash FROM events WHERE job_id=? ORDER BY seq", (jid,)).fetchall()
                    return self.send_json(200, [dict(e) for e in events])
                return self.send_json(200, job_dict(row))
        if parsed.path.startswith("/preview/"):
            pieces = parsed.path.split("/", 3)
            jid = pieces[2] if len(pieces) > 2 else ""
            raw = pieces[3] if len(pieces) > 3 else ""
            with connect() as db:
                row = db.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
            path = safe_preview_file(jid, raw) if row and row["status"] == "running" else None
            if not path:
                return self.send_json(404, {"error": "published file not found"})
            return self.file_response(path)
        return self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            if self.path == "/api/jobs":
                body = self.body_json()
                if set(body) - {"source_dir"}:
                    return self.send_json(400, {"error": "accepted field: source_dir"})
                item, duplicate = create_job(str(body.get("source_dir", "")), self.headers.get("Idempotency-Key", ""))
                return self.send_json(200 if duplicate else 202, {"job": item, "idempotent_replay": duplicate})
            parts = self.path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cancel":
                jid = parts[2]
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    row = db.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
                    if not row:
                        db.rollback(); return self.send_json(404, {"error": "job not found"})
                    try:
                        transition(db, jid, "cancelled", {"requested_by": "local_operator"})
                    except ValueError as exc:
                        db.rollback(); return self.send_json(409, {"error": str(exc)})
                    db.commit()
                return self.send_json(200, {"id": jid, "status": "cancelled"})
            if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "retry":
                jid = parts[2]
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    row = db.execute("SELECT status,attempt,max_attempts FROM jobs WHERE id=?", (jid,)).fetchone()
                    if not row:
                        db.rollback(); return self.send_json(404, {"error": "job not found"})
                    if row["status"] != "failed" or row["attempt"] >= row["max_attempts"]:
                        db.rollback(); return self.send_json(409, {"error": "job is not retryable"})
                    transition(db, jid, "queued", {"requested_by": "local_operator"})
                    db.commit()
                return self.send_json(202, {"id": jid, "status": "queued"})
            return self.send_json(404, {"error": "not found"})
        except Conflict as exc:
            return self.send_json(409, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            return self.send_json(500, {"error": str(exc)})

    def file_response(self, path: Path) -> None:
        try:
            raw = path.read_bytes()
        except OSError:
            return self.send_json(404, {"error": "file not found"})
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'none'; form-action 'none'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(raw)


PAGE = r'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WOLF DEPLOY · Runtime</title><style>
:root{color-scheme:dark;--bg:#09111d;--panel:#111d2b;--line:#293d52;--text:#e7f0f8;--muted:#91a6ba;--cyan:#55d8e8;--green:#58d6a3;--amber:#f4c264;--red:#ff7887}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 80% 0,#19324a,transparent 45%),var(--bg);font:15px/1.55 system-ui;color:var(--text)}main{max-width:1200px;padding:24px;margin:auto}header,.row,.title{display:flex;justify-content:space-between;align-items:center;gap:15px}h1{font-size:23px;margin:0}.muted{color:var(--muted);font-size:13px}.badge{border:1px solid #625127;border-radius:99px;padding:5px 10px;color:var(--amber);font-size:12px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}.card{background:#111d2bde;border:1px solid var(--line);border-radius:14px;padding:16px}.num{font-size:28px;font-weight:750}.cyan{color:var(--cyan)}.green{color:var(--green)}.red{color:var(--red)}button,input{font:inherit;color:inherit}button{background:#163043;border:1px solid #276174;border-radius:9px;padding:9px 13px;cursor:pointer}button:hover{border-color:var(--cyan)}input{background:#091522;border:1px solid var(--line);border-radius:8px;padding:9px;min-width:0;flex:1}.form{display:flex;gap:8px;margin:12px 0}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:right;border-bottom:1px solid var(--line);padding:10px 8px;vertical-align:top}.status{font-weight:700}.queued{color:var(--amber)}.building,.deploying{color:var(--cyan)}.running{color:var(--green)}.failed,.cancelled{color:var(--red)}a{color:var(--cyan)}pre{white-space:pre-wrap;color:var(--muted);font-size:12px}.notice{border-right:3px solid var(--cyan);padding:10px 12px;background:#0c2631;border-radius:7px;margin:12px 0}@media(max-width:760px){main{padding:14px}.grid{grid-template-columns:repeat(2,1fr)}header{align-items:flex-start;flex-direction:column}.tablewrap{overflow:auto}}
</style></head><body><main><header><div><h1>🐺 WOLF DEPLOY <span class="cyan">/ Runtime Core</span></h1><div class="muted">نشر محلي لمواقع ثابتة · حالة تشغيل وسجل دائم</div></div><span class="badge">محلي فقط · لا أوامر Shell</span></header><div class="notice">هذه النسخة تنشر ملفات HTML/CSS/JS محليًا. لا تدّعي نشر Docker أو Kubernetes. اختر مجلدًا داخل <code>projects/</code> يحتوي <code>index.html</code>.</div><section class="grid"><article class="card"><div class="muted">Queued</div><div id="queued" class="num">0</div></article><article class="card"><div class="muted">In progress</div><div id="active" class="num cyan">0</div></article><article class="card"><div class="muted">Running</div><div id="running" class="num green">0</div></article><article class="card"><div class="muted">Failed</div><div id="failed" class="num red">0</div></article></section><section class="card"><div class="title"><div><b>إنشاء عملية نشر محلية</b><div class="muted">مثال المجلد: example-site</div></div></div><div class="form"><input id="source" value="example-site" aria-label="اسم مجلد المشروع"><button id="deploy">ابدأ النشر</button></div><div id="message" class="muted"></div></section><section class="card" style="margin-top:14px"><div class="title"><div><b>عمليات التنفيذ</b><div class="muted">تحديث تلقائي · المصدر SQLite WAL</div></div><button id="refresh">تحديث</button></div><div class="tablewrap"><table><thead><tr><th>الحالة</th><th>المصدر</th><th>المحاولة</th><th>أُنشئت</th><th>الخطأ / المعاينة</th><th>الإجراءات</th></tr></thead><tbody id="jobs"></tbody></table></div></section><section class="card" style="margin-top:14px"><b>ضمانات النواة الحالية</b><pre>SQLite WAL · idempotency key · state-transition validation · worker lease · lease reconciliation · per-job hash-chained events · bounded static artifact copy</pre><div class="muted">للإنتاج متعدد العقد: يلزم استبدال SQLite بمخزن مشترك مثل PostgreSQL، وإضافة مصادقة ومزوّد نشر موثوق. هذا غير موجود بعد.</div></section></main><script>
const $=id=>document.getElementById(id);const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));async function api(path,opt={}){const r=await fetch(path,opt);let d;try{d=await r.json()}catch{d={}}if(!r.ok)throw Error(d.error||`HTTP ${r.status}`);return d}async function refresh(){try{const jobs=await api('/api/jobs');const counts={queued:0,active:0,running:0,failed:0};jobs.forEach(j=>{if(j.status==='queued')counts.queued++;else if(['building','deploying'].includes(j.status))counts.active++;else if(j.status==='running')counts.running++;else if(j.status==='failed')counts.failed++});Object.entries(counts).forEach(([k,v])=>$(k).textContent=v);$('jobs').innerHTML=jobs.map(j=>`<tr><td class="status ${esc(j.status)}">${esc(j.status)}</td><td>${esc(j.source_path)}</td><td>${j.attempt}/${j.max_attempts}</td><td>${new Date(j.created_at).toLocaleString('ar')}</td><td>${j.preview_path?`<a target="_blank" rel="noopener" href="${esc(j.preview_path)}">فتح المعاينة</a>`:esc(j.error||'—')}</td><td>${j.status==='failed'&&j.attempt<j.max_attempts?`<button data-retry="${esc(j.id)}">إعادة</button>`:''}${['queued','building','deploying'].includes(j.status)?` <button data-cancel="${esc(j.id)}">إلغاء</button>`:''} <button data-events="${esc(j.id)}">الأحداث</button></td></tr>`).join('')||'<tr><td colspan="6" class="muted">لا توجد عمليات بعد.</td></tr>'}catch(e){$('message').textContent=e.message}}
$('deploy').onclick=async()=>{const b=$('deploy');b.disabled=true;try{const d=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({source_dir:$('source').value.trim()})});$('message').textContent=`تم قبول العملية ${d.job.id} · ${d.job.status}`;await refresh()}catch(e){$('message').textContent=e.message}finally{b.disabled=false}};$('refresh').onclick=refresh;$('jobs').onclick=async e=>{const b=e.target.closest('button');if(!b)return;try{if(b.dataset.retry)await api(`/api/jobs/${b.dataset.retry}/retry`,{method:'POST'});else if(b.dataset.cancel)await api(`/api/jobs/${b.dataset.cancel}/cancel`,{method:'POST'});else if(b.dataset.events){const x=await api(`/api/jobs/${b.dataset.events}/events`);$('message').textContent=x.map(v=>`${v.created_at} · ${v.event_type} · ${v.from_status||'—'} → ${v.to_status||'—'}`).join(' | ')}await refresh()}catch(err){$('message').textContent=err.message}};refresh();setInterval(refresh,2000);
</script></body></html>'''


def main() -> None:
    init_db()
    worker = threading.Thread(target=worker_loop, name="wolf-worker", daemon=True)
    worker.start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(json.dumps({"event": "runtime_started", "host": HOST, "port": PORT,
                      "projects_root": str(ROOT), "published_root": str(PUBLISHED), "worker": WORKER_ID}), flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        STOP.set(); server.shutdown(); server.server_close(); worker.join(timeout=3)


if __name__ == "__main__":
    main()