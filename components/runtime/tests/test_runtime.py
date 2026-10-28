import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import runtime


class RuntimeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        runtime.ROOT = root / "projects"
        runtime.PUBLISHED = root / "published"
        runtime.DB_PATH = root / "runtime.sqlite3"
        runtime.LEASE_SECONDS = 4
        runtime.init_db()
        (runtime.ROOT / "site-a").mkdir(parents=True)
        (runtime.ROOT / "site-a" / "index.html").write_text("<h1>actual local publish</h1>", encoding="utf-8")
        runtime.STOP.clear()
        cls.worker = threading.Thread(target=runtime.worker_loop, daemon=True)
        cls.worker.start()
        cls.server = runtime.ThreadingHTTPServer(("127.0.0.1", 0), runtime.Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        runtime.STOP.set()
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=2)
        cls.server_thread.join(timeout=2)
        cls.temp.cleanup()

    def request(self, path, method="GET", body=None, key=None):
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if key:
            headers["Idempotency-Key"] = key
        req = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=3) as res:
                return res.status, json.loads(res.read()) if "json" in res.headers.get("Content-Type", "") else res.read().decode()
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_idempotency_and_conflict(self):
        status1, first = self.request("/api/jobs", "POST", {"source_dir": "site-a"}, "same-key")
        status2, second = self.request("/api/jobs", "POST", {"source_dir": "site-a"}, "same-key")
        self.assertEqual(status1, 202)
        self.assertEqual(status2, 200)
        self.assertEqual(first["job"]["id"], second["job"]["id"])
        (runtime.ROOT / "site-b").mkdir()
        (runtime.ROOT / "site-b" / "index.html").write_text("B", encoding="utf-8")
        status3, _ = self.request("/api/jobs", "POST", {"source_dir": "site-b"}, "same-key")
        self.assertEqual(status3, 409)

    def test_deploy_preview_and_audit_hash_chain(self):
        status, created = self.request("/api/jobs", "POST", {"source_dir": "site-a"}, "deploy-test")
        self.assertEqual(status, 202)
        jid = created["job"]["id"]
        deadline = time.time() + 5
        item = None
        while time.time() < deadline:
            _, item = self.request(f"/api/jobs/{jid}")
            if item["status"] in {"running", "failed"}:
                break
            time.sleep(.05)
        self.assertEqual(item["status"], "running", item)
        code, html = self.request(item["preview_path"])
        self.assertEqual(code, 200)
        self.assertIn("actual local publish", html)
        _, events = self.request(f"/api/jobs/{jid}/events")
        previous = "GENESIS"
        for event in events:
            payload = json.dumps({"job_id": jid, "type": event["event_type"],
                                  "from": event["from_status"], "to": event["to_status"],
                                  "detail": json.loads(event["detail"]), "created_at": event["created_at"]},
                                 sort_keys=True, separators=(",", ":"))
            import hashlib
            expected = hashlib.sha256((previous + "|" + payload).encode()).hexdigest()
            self.assertEqual(event["prev_hash"], previous)
            self.assertEqual(event["hash"], expected)
            previous = expected

    def test_path_escape_rejected(self):
        status, body = self.request("/api/jobs", "POST", {"source_dir": "../kn92-core"}, "escape-test")
        self.assertEqual(status, 400)
        self.assertIn("inside WOLF_PROJECTS_ROOT", body["error"])

    def test_publish_rejects_hidden_secrets_and_symlinks(self):
        site = runtime.ROOT / "unsafe-site"
        site.mkdir()
        (site / "index.html").write_text("ok", encoding="utf-8")
        (site / ".env").write_text("SECRET=never-publish", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hidden files"):
            runtime.validate_static_site(site)
        (site / ".env").unlink()
        try:
            (site / "link.html").symlink_to(site / "index.html")
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaisesRegex(ValueError, "symbolic links"):
            runtime.validate_static_site(site)

    def test_dashboard_and_health(self):
        with urlopen(self.base + "/", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("WOLF DEPLOY", response.read().decode())
        status, health = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")


if __name__ == "__main__":
    unittest.main()
