using System.Text.Json;
using Microsoft.Data.Sqlite;

// Executable store-level CONTRACT tests, not UER Docker acceptance tests.
// Run in a sandbox with .NET 8: dotnet run --project tests/Uer.Api.StoreContracts
var checks = new (string Name, Action Test)[] {
    ("S-01-atomic-claim-audit", TestClaim),
    ("S-02-state-fencing", TestTransitions),
    ("S-03-stale-completion-rejected", TestStaleCompletion),
    ("S-04-quarantine-idempotent", TestQuarantine),
    ("S-05-recovery-audit-tamper", TestRecoveryAuditTamper),
    ("S-06-lifecycle-audit-tamper", TestLifecycleAuditTamper),
    ("S-07-cleanup-observation-audit", TestCleanupObservation),
    ("S-08-ledger-tamper", TestLedgerTamper),
    ("S-09-completion-requires-cleanup", TestCompletionRequiresCleanup),
};
var failed=0;
foreach(var (name,test) in checks) {
    try { test(); Console.WriteLine(JsonSerializer.Serialize(new{test=name,status="PASS"})); }
    catch(Exception ex) { failed++;Console.WriteLine(JsonSerializer.Serialize(new{test=name,status="FAIL",error=ex.ToString()})); }
}
Console.WriteLine(JsonSerializer.Serialize(new{suite="UER_STORE_CONTRACTS",total=checks.Length,passed=checks.Length-failed,failed,
  scope="LOCAL_SQLITE_STORE_NO_DOCKER", acceptance_counted=false}));
return failed==0?0:1;

static (Store db,string dbfile,string jobId) Create(string suffix) {
    var dir=Path.Combine(Path.GetTempPath(),"uer-store-contract-"+Guid.NewGuid().ToString("N"));
    Directory.CreateDirectory(dir);
    var file=Path.Combine(dir,"uer.db");
    var store=new Store(file);
    var job="job-"+suffix+"-"+Guid.NewGuid().ToString("N");
    store.New(job,"node-sample");
    return (store,file,job);
}
static AttemptInfo Claimed(Store db,string job) => db.TryClaim(job) ?? throw new Exception("claim failed");
static void Ensure(bool condition,string detail) {
    if(!condition)throw new Exception(detail);
}
static int Count(string file,string table) {
    // table name is chosen from constants inside this test, never user input
    var allowed=new[]{"ledger","attempts","lifecycle_audit","recovery_audit"};
    if(!allowed.Contains(table)) throw new Exception("Disallowed table");
    using var c=new SqliteConnection($"Data Source={file}");c.Open();
    using var cmd=c.CreateCommand();cmd.CommandText="SELECT COUNT(*) FROM "+table;
    return Convert.ToInt32(cmd.ExecuteScalar());
}
static void Tamper(string file,string sql) {
    using var c=new SqliteConnection($"Data Source={file}");c.Open();
    using var cmd=c.CreateCommand();cmd.CommandText=sql;
    Ensure(cmd.ExecuteNonQuery()>0,"tampering did not modify a row");
}
static AttemptInfo Running(Store db,string job) {
    var a=Claimed(db,job);
    Ensure(db.MarkContainerCreated(a),"container-created rejected");
    Ensure(db.MarkRunning(a),"running rejected");
    return a;
}
static void TestClaim() {
    var(db,file,id)=Create("claim");
    var a=Claimed(db,id);
    Ensure(db.TryClaim(id) is null,"double claim permitted");
    Ensure(Count(file,"attempts")==1,"attempt count wrong");
    Ensure(Count(file,"lifecycle_audit")==2,"created and claim audit missing");
    Ensure(db.VerifyLifecycleAudit(),"audit invalid");
    Ensure(db.Job(id)?.Status=="claimed","claim state wrong");
}
static void TestTransitions() {
    var(db,_,id)=Create("states");
    var a=Claimed(db,id);
    Ensure(!db.MarkRunning(a),"running before create permitted");
    Ensure(db.MarkContainerCreated(a),"create rejected");
    Ensure(!db.MarkContainerCreated(a),"duplicate create permitted");
    Ensure(db.MarkRunning(a),"run rejected");
    Ensure(!db.MarkRunning(a),"duplicate run permitted");
    Ensure(db.VerifyLifecycleAudit(),"lifecycle invalid");
}
static void TestStaleCompletion() {
    var(db,file,id)=Create("stale");
    var a=Running(db,id);
    var now=DateTimeOffset.UtcNow.ToString("O");
    Ensure(db.RecordCleanupEvidence(a),"cleanup evidence missing");
    Ensure(db.Complete(a,"node-sample","manifest-hash","image-digest",now,now,0,"artifact",null),"completion failed");
    Ensure(!db.Complete(a,"node-sample","manifest-hash","image-digest",now,now,0,"artifact",null),"duplicate completion accepted");
    Ensure(db.Job(id)?.Status=="passed","job not passed");
    Ensure(Count(file,"ledger")==1,"duplicate ledger record");
    Ensure(db.Verify() && db.VerifyLifecycleAudit(),"verification failed");
}
static void TestQuarantine() {
    var(db,_,id)=Create("quarantine");
    var a=Running(db,id);
    Ensure(db.Quarantine(a,"incomplete docker evidence"),"quarantine failed");
    Ensure(!db.Quarantine(a,"again"),"double quarantine permitted");
    Ensure(db.Job(id)?.Status=="quarantined","not quarantined");
    Ensure(db.VerifyLifecycleAudit() && db.VerifyRecoveryAudit(),"quarantine audits invalid");
    Ensure(!db.MarkRunning(a),"quarantined running transition accepted");
}
static void TestRecoveryAuditTamper() {
    var(db,file,id)=Create("recovery-tamper");
    var a=Claimed(db,id);
    Ensure(db.Quarantine(a,"unverified recovery"),"quarantine failed");
    Ensure(db.VerifyRecoveryAudit(),"recovery audit baseline failed");
    Tamper(file,"UPDATE recovery_audit SET evidence='forged' WHERE seq=1");
    Ensure(!db.VerifyRecoveryAudit(),"recovery audit tamper undetected");
}
static void TestLifecycleAuditTamper() {
    var(db,file,id)=Create("lifecycle-tamper");
    Claimed(db,id);
    Ensure(db.VerifyLifecycleAudit(),"lifecycle baseline failed");
    Tamper(file,"UPDATE lifecycle_audit SET evidence='forged' WHERE seq=1");
    Ensure(!db.VerifyLifecycleAudit(),"lifecycle tamper undetected");
}
static void TestCleanupObservation() {
    var(db,file,id)=Create("cleanup");
    var a=Running(db,id);
    Ensure(db.RecordCleanupEvidence(a),"cleanup evidence append rejected");
    Ensure(db.VerifyLifecycleAudit(),"audit of cleanup evidence invalid");
    Ensure(Count(file,"lifecycle_audit")==5,"cleanup event absent");
    // This is a store contract: it does NOT prove Docker was cleaned up.
}
static void TestLedgerTamper() {
    var(db,file,id)=Create("ledger-tamper");
    var a=Running(db,id);
    var now=DateTimeOffset.UtcNow.ToString("O");
    Ensure(db.RecordCleanupEvidence(a),"cleanup evidence missing");
    Ensure(db.Complete(a,"node-sample","manifest-hash","image-digest",now,now,1,"artifact","test failed"),"completion failed");
    Ensure(db.Verify(),"ledger baseline failed");
    Tamper(file,"UPDATE ledger SET artifact_sha256='forged' WHERE seq=1");
    Ensure(!db.Verify(),"ledger tamper undetected");
}

static void TestCompletionRequiresCleanup() {
    var(db,file,id)=Create("cleanup-gate");
    var a=Running(db,id);
    var now=DateTimeOffset.UtcNow.ToString("O");
    Ensure(!db.Complete(a,"node-sample","manifest-hash","image-digest",now,now,0,"artifact",null),
           "completion succeeded without cleanup proof");
    Ensure(Count(file,"ledger")==0,"ledger committed despite missing cleanup");
    Ensure(db.RecordCleanupEvidence(a),"record cleanup evidence failed");
    Ensure(db.Complete(a,"node-sample","manifest-hash","image-digest",now,now,0,"artifact",null),
           "completion rejected after cleanup evidence");
    Ensure(db.VerifyLifecycleAudit() && db.Verify(),"audit invalid");
}
