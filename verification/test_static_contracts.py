"""Source-level regression checks. NOT C# build/behavior verification."""
from pathlib import Path
import unittest
import sqlite3
import tempfile
import hashlib

ROOT=Path(__file__).resolve().parents[1]
PROGRAM=ROOT/"source/blackwolf-uer-v0.1.1-reliability/src/Uer.Api/Program.cs"
CONTRACTS=ROOT/"tests/Uer.Api.StoreContracts/Program.cs"

class SourceContractChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=PROGRAM.read_text()
        cls.c=CONTRACTS.read_text()

    def test_source_present(self): self.assertTrue(PROGRAM.is_file())
    def test_lifecycle_verifier(self):
        self.assertIn("VerifyLifecycleAudit()",self.s)
        self.assertIn('SELECT id,status FROM jobs',self.s)
        self.assertIn('SELECT job_id,attempt_id,epoch,state FROM attempts',self.s)
    def test_claim_audited_within_sqlite_transaction(self):
        body=self.s[self.s.index("public AttemptInfo? TryClaim("):self.s.index("public List<AttemptInfo> InterruptedAttempts()")]
        self.assertLess(body.index("tx=c.BeginTransaction()"),body.index("AppendLifecycle("))
        self.assertLess(body.index("AppendLifecycle("),body.index("tx.Commit()"))
    def test_transition_atomic_with_audit(self):
        body=self.s[self.s.index("private bool Transition("):self.s.index("public bool Reconcile(")]
        self.assertLess(body.index("UPDATE jobs"),body.index("UPDATE attempts"))
        self.assertLess(body.index("UPDATE attempts"),body.index("AppendLifecycle("))
        self.assertLess(body.index("AppendLifecycle("),body.index("tx.Commit()"))
    def test_recovery_audit_has_chain(self):
        self.assertIn("public bool VerifyRecoveryAudit()",self.s)
        self.assertIn('AppendLifecycle(c,tx,a.JobId,a.AttemptId,a.Epoch,before.job',self.s)
    def test_cleanup_identity_before_removal(self):
        body=self.s[self.s.index("public static async Task CleanupContainer("):self.s.index("private static void WriteFailureEvidence(")]
        self.assertIn("ContainerPresent(a,ct)",body)
        self.assertIn('["rm","-f",a.ContainerName]',body)
        self.assertLess(body.index("ContainerPresent(a,ct)"),body.index('["rm","-f",a.ContainerName]'))
        self.assertGreater(body.count("ContainerPresent(a,ct)"),1)
    def test_docker_identity_labels(self):
        body=self.s[self.s.index("public static async Task<bool> ContainerPresent("):self.s.index("public static async Task CleanupContainer(")]
        for k in ["blackwolf.uer","blackwolf.job_id","blackwolf.attempt_id","blackwolf.execution_epoch"]:
            self.assertIn(k,body)
        self.assertIn("byName!=byLabel",body)
        self.assertIn("JsonDocument.Parse",body)
    def test_failure_path_is_quarantine_not_complete(self):
        body=self.s[self.s.index("public async Task Execute(AttemptInfo attempt"):self.s.index("sealed class Worker")]
        self.assertIn("QuarantineFailClosed(attempt",body)
        self.assertEqual(body.count("db.Complete("),1)
        self.assertIn("RecordCleanupEvidence(attempt)",body)
        self.assertLess(body.index("RecordCleanupEvidence(attempt)"),body.index("db.Complete("))
        self.assertIn("catch(Exception ex)",body)
        # After 'catch(Exception ex)' only quarantine, never commit an unverified result
        final_catch=body.rindex("catch(Exception ex)")
        self.assertNotIn("db.Complete(",body[final_catch:])
    def test_terminal_result_requires_cleanup_in_store(self):
        body=self.s[self.s.index("public bool Complete("):self.s.index("private SqliteConnection Open()")]
        self.assertIn("container_absence_verified",body)
        self.assertLess(body.index("container_absence_verified"),body.index("INSERT INTO ledger"))
    def test_recovery_fail_closed(self):
        body=self.s[self.s.index("sealed class Worker"): ]
        self.assertIn("await Runner.CleanupContainer(a,stoppingToken)",body)
        self.assertIn("retrySafetyProven:false",body)
        self.assertIn("db.Reconcile(a,decision",body)
    def test_worker_stops_if_quarantine_not_persisted(self):
        self.assertIn("FATAL: worker quarantine could not be persisted",self.s)
        self.assertIn("FATAL: recovery quarantine could not be persisted",self.s)
    def test_store_contracts_defined(self):
        self.assertEqual(self.c.count('("S-'),9)
        for scenario in ("TestClaim","TestTransitions","TestStaleCompletion","TestQuarantine",
                         "TestRecoveryAuditTamper","TestLifecycleAuditTamper","TestCleanupObservation",
                         "TestLedgerTamper","TestCompletionRequiresCleanup"):
            self.assertIn("static void "+scenario+"()",self.c)
    def test_dotnet_build_artifacts(self):
        self.assertTrue((ROOT/"source/blackwolf-uer-v0.1.1-reliability/src/Uer.Api/Uer.Api.csproj").is_file())
        self.assertTrue((ROOT/"tests/Uer.Api.StoreContracts/Uer.Api.StoreContracts.csproj").is_file())

class SqliteEngineSemantics(unittest.TestCase):
    """Tests Python SQLite rollback semantics only; they do NOT execute the C# Store."""
    def test_state_and_audit_rollback_together(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/"probe.db"
            with sqlite3.connect(db) as c:
                c.executescript('CREATE TABLE state(id INTEGER PRIMARY KEY,status TEXT);'
                                'CREATE TABLE audit(id INTEGER PRIMARY KEY,event TEXT);'
                                "INSERT INTO state VALUES(1,'claimed');")
            c=sqlite3.connect(db,isolation_level=None)
            try:
                c.execute("BEGIN IMMEDIATE")
                c.execute("UPDATE state SET status='running' WHERE id=1")
                c.execute("INSERT INTO audit(event) VALUES('running')")
                raise RuntimeError("injected")
            except RuntimeError:
                c.execute("ROLLBACK")
            finally: c.close()
            with sqlite3.connect(db) as c:
                self.assertEqual(c.execute("SELECT status FROM state").fetchone()[0],"claimed")
                self.assertEqual(c.execute("SELECT COUNT(*) FROM audit").fetchone()[0],0)
    def test_state_and_audit_commit_together(self):
        with sqlite3.connect(":memory:") as c:
            c.execute("CREATE TABLE state(status TEXT)")
            c.execute("CREATE TABLE audit(event TEXT)")
            c.execute("INSERT INTO state VALUES('claimed')")
            c.commit()  # create commit boundary
            c.execute("BEGIN IMMEDIATE")
            c.execute("UPDATE state SET status='running'")
            c.execute("INSERT INTO audit VALUES('running')")
            c.commit()
            self.assertEqual(c.execute("SELECT status FROM state").fetchone()[0],"running")
            self.assertEqual(c.execute("SELECT event FROM audit").fetchone()[0],"running")

if __name__=="__main__":
    unittest.main(verbosity=2)
