using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading.Channels;
using System.Globalization;
using Microsoft.Data.Sqlite;

var builder = WebApplication.CreateBuilder(args);
var root = Path.GetFullPath(builder.Configuration["UER_ROOT"] ?? Path.Combine(Directory.GetCurrentDirectory(), "data"));
var projects = Path.GetFullPath(builder.Configuration["UER_PROJECTS"] ?? Path.Combine(Directory.GetCurrentDirectory(), "projects"));
Directory.CreateDirectory(root);
var store = new Store(Path.Combine(root, "uer.db"));
// SQLite is the durable queue; Channel only signals that new work may exist.
var queue = Channel.CreateBounded<string>(new BoundedChannelOptions(32) { FullMode = BoundedChannelFullMode.DropWrite, SingleReader = true });
builder.Services.AddSingleton(store);
builder.Services.AddSingleton(queue);
builder.Services.AddSingleton(new Runner(root, projects, store, queue));
builder.Services.AddHostedService<Worker>();
var app = builder.Build();
// API is deliberately loopback-only for this local MVP.
app.Use(async (ctx, next) => { if (ctx.Connection.RemoteIpAddress is not { } ip || !System.Net.IPAddress.IsLoopback(ip)) { ctx.Response.StatusCode = 403; return; } await next(); });
app.MapGet("/health", () => Results.Ok(new { status = "ok" }));
app.MapGet("/projects", () => Results.Ok(Directory.Exists(projects) ? Directory.GetDirectories(projects).Select(Path.GetFileName).OrderBy(x => x).ToArray() : Array.Empty<string?>()));
app.MapPost("/jobs", async (Submit req, Runner runner, CancellationToken ct) => {
    try { var id = await runner.Submit(req.Project, ct); return Results.Accepted($"/jobs/{id}", new { job_id = id }); }
    catch (Exception e) when (e is ArgumentException or InvalidOperationException) { return Results.BadRequest(new { error = e.Message }); }
});
app.MapPost("/jobs/{id}/replay", async (string id, Runner runner, CancellationToken ct) => {
    try { var newId = await runner.Replay(id, ct); return Results.Accepted($"/jobs/{newId}", new { job_id = newId }); }
    catch (Exception e) when (e is ArgumentException or InvalidOperationException) { return Results.BadRequest(new { error = e.Message }); }
});
app.MapGet("/jobs/{id}", (string id, Store db) => db.Job(id) is { } j ? Results.Ok(j) : Results.NotFound());
app.MapGet("/ledger/verify", (Store db) => Results.Ok(new { valid = db.Verify() }));
app.MapGet("/recovery-audit/verify", (Store db) => Results.Ok(new { valid = db.VerifyRecoveryAudit() }));
app.MapGet("/ledger", (Store db) => Results.Ok(db.Records()));
app.Run();

record Submit(string Project);
record Manifest(string Project, string Runtime, string Operation, int TimeoutSeconds = 120, int MemoryMb = 256, int Cpu = 1);
record AttemptInfo(string JobId,string AttemptId,long Epoch,string ContainerName,string State);
enum RecoveryDecision { SafeToRetry, VerifiedCompletion, InsufficientEvidence }
static class RecoveryPolicy {
    public static RecoveryDecision EvaluateRecovery(bool previousExecutionTerminated,bool retrySafetyProven,bool completionVerified) {
        if(completionVerified)return RecoveryDecision.VerifiedCompletion;
        if(previousExecutionTerminated && retrySafetyProven)return RecoveryDecision.SafeToRetry;
        return RecoveryDecision.InsufficientEvidence;
    }
}
record JobInfo(string Id, string Project, string Status, string? ExitCode, string? Error, string? ImageDigest, string? ArtifactSha256);
sealed class Store {
    private readonly string cs; private readonly object gate = new();
    public Store(string file) { cs = new SqliteConnectionStringBuilder { DataSource = file }.ToString(); using var c = Open();
        using var cmd = c.CreateCommand(); cmd.CommandText = """
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project TEXT NOT NULL, status TEXT NOT NULL, exit_code INTEGER, error TEXT, image_digest TEXT, artifact_sha256 TEXT, attempt INTEGER NOT NULL DEFAULT 0, attempt_id TEXT);
        CREATE TABLE IF NOT EXISTS attempts(job_id TEXT NOT NULL,attempt_id TEXT NOT NULL PRIMARY KEY,epoch INTEGER NOT NULL,container_name TEXT NOT NULL UNIQUE,state TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(job_id) REFERENCES jobs(id));
        CREATE UNIQUE INDEX IF NOT EXISTS ux_attempt_epoch ON attempts(job_id,epoch);
        CREATE TABLE IF NOT EXISTS recovery_audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT NOT NULL,attempt_id TEXT NOT NULL,epoch INTEGER NOT NULL,decision TEXT NOT NULL,evidence TEXT NOT NULL,previous_hash TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lifecycle_audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT NOT NULL,attempt_id TEXT NOT NULL,epoch INTEGER NOT NULL,event TEXT NOT NULL,evidence TEXT NOT NULL,previous_hash TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ledger(seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, project_id TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, container_image_digest TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT NOT NULL, exit_code INTEGER NOT NULL, artifact_sha256 TEXT NOT NULL, previous_record_hash TEXT NOT NULL, record_hash TEXT NOT NULL);
        """; cmd.ExecuteNonQuery();
        using var columns=c.CreateCommand();columns.CommandText="PRAGMA table_info(jobs)";using(var rd=columns.ExecuteReader()){var found=false;while(rd.Read())if(rd.GetString(1)=="attempt_id")found=true;if(!found){using var migration=c.CreateCommand();migration.CommandText="ALTER TABLE jobs ADD COLUMN attempt_id TEXT";migration.ExecuteNonQuery();}}
    }
    // The job claim and preselected Docker identity commit atomically.
    public AttemptInfo? TryClaim(string id) { lock(gate) { using var c=Open();using var tx=c.BeginTransaction();using var cmd=c.CreateCommand();cmd.Transaction=tx;
        var attempt=Guid.NewGuid().ToString("N");var name="uer-"+attempt;
        cmd.CommandText="UPDATE jobs SET status='claimed',attempt=attempt+1,attempt_id=$aid,error=NULL WHERE id=$id AND status='queued'";
        cmd.Parameters.AddWithValue("$id",id);cmd.Parameters.AddWithValue("$aid",attempt);if(cmd.ExecuteNonQuery()!=1)return null;
        cmd.CommandText="SELECT attempt FROM jobs WHERE id=$id";var epoch=(long)cmd.ExecuteScalar()!;
        cmd.CommandText="INSERT INTO attempts(job_id,attempt_id,epoch,container_name,state,created_at) VALUES($id,$aid,$epoch,$name,'claimed',$now)";
        cmd.Parameters.AddWithValue("$epoch",epoch);cmd.Parameters.AddWithValue("$name",name);cmd.Parameters.AddWithValue("$now",DateTimeOffset.UtcNow.ToString("O"));cmd.ExecuteNonQuery();AppendLifecycleAudit(c,tx,id,attempt,epoch,"claimed",name);tx.Commit();return new(id,attempt,epoch,name,"claimed");
    } }
    public List<AttemptInfo> InterruptedAttempts(){lock(gate){using var c=Open();using var cmd=c.CreateCommand();cmd.CommandText="SELECT a.job_id,a.attempt_id,a.epoch,a.container_name,a.state FROM attempts a JOIN jobs j ON j.id=a.job_id WHERE j.status IN ('claimed','container_created','running','reconciling') AND a.state IN ('claimed','container_created','running','reconciling') AND j.attempt_id=a.attempt_id AND j.attempt=a.epoch ORDER BY a.created_at";using var rd=cmd.ExecuteReader();var result=new List<AttemptInfo>();while(rd.Read())result.Add(new(rd.GetString(0),rd.GetString(1),rd.GetInt64(2),rd.GetString(3),rd.GetString(4)));return result;}}
    public bool MarkContainerCreated(AttemptInfo a)=>Transition(a,"claimed","container_created");
    public bool MarkRunning(AttemptInfo a)=>Transition(a,"container_created","running");
    private bool Transition(AttemptInfo a,string expected,string next){lock(gate){using var c=Open();using var tx=c.BeginTransaction();using var cmd=c.CreateCommand();cmd.Transaction=tx;
        cmd.Parameters.AddWithValue("$id",a.JobId);cmd.Parameters.AddWithValue("$aid",a.AttemptId);cmd.Parameters.AddWithValue("$epoch",a.Epoch);cmd.Parameters.AddWithValue("$expected",expected);cmd.Parameters.AddWithValue("$next",next);
        cmd.CommandText="UPDATE jobs SET status=$next WHERE id=$id AND attempt_id=$aid AND attempt=$epoch AND status=$expected AND EXISTS(SELECT 1 FROM attempts WHERE job_id=$id AND attempt_id=$aid AND epoch=$epoch AND state=$expected)";
        if(cmd.ExecuteNonQuery()!=1)return false;
        cmd.CommandText="UPDATE attempts SET state=$next WHERE job_id=$id AND attempt_id=$aid AND epoch=$epoch AND state=$expected";
        if(cmd.ExecuteNonQuery()!=1)throw new InvalidOperationException("Attempt transition rejected");AppendLifecycleAudit(c,tx,a.JobId,a.AttemptId,a.Epoch,next,a.ContainerName);tx.Commit();return true;
    }}
    // Every recovery transition is fenced, checked for exactly one affected row, and audited atomically.
    public bool Reconcile(AttemptInfo a,RecoveryDecision decision,string evidence) { lock(gate) { using var c=Open();using var tx=c.BeginTransaction();using var cmd=c.CreateCommand();cmd.Transaction=tx;
        if(string.IsNullOrWhiteSpace(evidence))throw new ArgumentException("Recovery evidence is required");
        var status=decision switch { RecoveryDecision.SafeToRetry=>"retry_eligible",RecoveryDecision.VerifiedCompletion=>"completed",_=>"quarantined" };
        var attemptState=decision switch { RecoveryDecision.SafeToRetry=>"retry_eligible",RecoveryDecision.VerifiedCompletion=>"completed",_=>"quarantined" };
        cmd.Parameters.AddWithValue("$id",a.JobId);cmd.Parameters.AddWithValue("$aid",a.AttemptId);cmd.Parameters.AddWithValue("$epoch",a.Epoch);
        cmd.Parameters.AddWithValue("$status",status);cmd.Parameters.AddWithValue("$evidence",evidence);cmd.Parameters.AddWithValue("$attemptState",attemptState);
        cmd.CommandText="UPDATE jobs SET status=$status,error=$evidence WHERE id=$id AND attempt=$epoch AND attempt_id=$aid AND status IN ('claimed','container_created','running','reconciling') AND EXISTS(SELECT 1 FROM attempts WHERE job_id=$id AND attempt_id=$aid AND epoch=$epoch AND state IN ('claimed','container_created','running','reconciling'))";
        if(cmd.ExecuteNonQuery()!=1)return false;
        cmd.CommandText="UPDATE attempts SET state=$attemptState WHERE job_id=$id AND attempt_id=$aid AND epoch=$epoch AND state IN ('claimed','container_created','running','reconciling')";
        if(cmd.ExecuteNonQuery()!=1)throw new InvalidOperationException("Recovery attempt update failed");
        cmd.CommandText="SELECT record_hash FROM recovery_audit ORDER BY seq DESC LIMIT 1";
        var prev=(string?)cmd.ExecuteScalar()??new string('0',64);
        var record=Hash(string.Join("\n",new[]{a.JobId,a.AttemptId,a.Epoch.ToString(CultureInfo.InvariantCulture),decision.ToString(),evidence,prev}));
        cmd.Parameters.AddWithValue("$decision",decision.ToString());cmd.Parameters.AddWithValue("$prev",prev);cmd.Parameters.AddWithValue("$record",record);
        cmd.CommandText="INSERT INTO recovery_audit(job_id,attempt_id,epoch,decision,evidence,previous_hash,record_hash) VALUES($id,$aid,$epoch,$decision,$evidence,$prev,$record)";
        if(cmd.ExecuteNonQuery()!=1)throw new InvalidOperationException("Recovery audit insert failed");
        AppendLifecycleAudit(c,tx,a.JobId,a.AttemptId,a.Epoch,"recovery:"+decision.ToString(),evidence);
        tx.Commit();return true;
    } }
    public bool Quarantine(AttemptInfo a,string reason)=>Reconcile(a,RecoveryDecision.InsufficientEvidence,reason);
    // Final state and audit append commit or roll back together.
    public bool Complete(AttemptInfo attempt,string project,string manifest,string image,string started,string finished,int exit,string artifact,string? error) {
      lock(gate) { using var c=Open(); using var tx=c.BeginTransaction(); using var cmd=c.CreateCommand();cmd.Transaction=tx;
        cmd.CommandText="SELECT status FROM jobs WHERE id=$id AND attempt=$epoch AND attempt_id=$aid AND EXISTS(SELECT 1 FROM attempts WHERE attempt_id=$aid AND job_id=$id AND epoch=$epoch AND state='running') AND EXISTS(SELECT 1 FROM lifecycle_audit WHERE job_id=$id AND attempt_id=$aid AND epoch=$epoch AND event='cleanup_evidence')";
        cmd.Parameters.AddWithValue("$id",attempt.JobId);cmd.Parameters.AddWithValue("$epoch",attempt.Epoch);cmd.Parameters.AddWithValue("$aid",attempt.AttemptId);
        if((string?)cmd.ExecuteScalar()!="running")return false;
        cmd.CommandText="SELECT record_hash FROM ledger ORDER BY seq DESC LIMIT 1";
        var prev=(string?)cmd.ExecuteScalar()??new string('0',64);
        var fields=new[]{attempt.JobId,project,manifest,image,started,finished,exit.ToString(CultureInfo.InvariantCulture),artifact,prev};
        var hash=Hash(string.Join("\n",fields));
        cmd.CommandText="INSERT INTO ledger(job_id,project_id,manifest_sha256,container_image_digest,started_at,finished_at,exit_code,artifact_sha256,previous_record_hash,record_hash) VALUES($id,$p,$m,$i,$s,$f,$e,$a,$prev,$hash)";
        cmd.Parameters.AddWithValue("$p",project);cmd.Parameters.AddWithValue("$m",manifest);cmd.Parameters.AddWithValue("$i",image);cmd.Parameters.AddWithValue("$s",started);cmd.Parameters.AddWithValue("$f",finished);cmd.Parameters.AddWithValue("$e",exit);cmd.Parameters.AddWithValue("$a",artifact);cmd.Parameters.AddWithValue("$prev",prev);cmd.Parameters.AddWithValue("$hash",hash);
        cmd.ExecuteNonQuery();
        cmd.CommandText="UPDATE jobs SET status=$status,exit_code=$e,error=$err,image_digest=$i,artifact_sha256=$a WHERE id=$id AND attempt=$epoch AND attempt_id=$aid AND status='running' AND EXISTS(SELECT 1 FROM attempts WHERE attempt_id=$aid AND job_id=$id AND epoch=$epoch AND state='running')";
        cmd.Parameters.AddWithValue("$status",error is null && exit==0?"passed":"failed");
        cmd.Parameters.AddWithValue("$err",(object?)error??DBNull.Value);
        if(cmd.ExecuteNonQuery()!=1)throw new InvalidOperationException("Final state update failed");
        cmd.CommandText="UPDATE attempts SET state='completed' WHERE job_id=$id AND attempt_id=$aid AND epoch=$epoch AND state='running'";if(cmd.ExecuteNonQuery()!=1)throw new InvalidOperationException("Completion attempt update failed");
        AppendLifecycleAudit(c,tx,attempt.JobId,attempt.AttemptId,attempt.Epoch,error is null && exit==0?"completed":"failed",artifact);
        tx.Commit();return true;
      }
    }
    private SqliteConnection Open() { var c = new SqliteConnection(cs); c.Open(); return c; }
    public List<string> Pending() { lock(gate) { using var c=Open(); using var cmd=c.CreateCommand(); cmd.CommandText="SELECT id FROM jobs WHERE status='queued' ORDER BY rowid"; using var rd=cmd.ExecuteReader(); var ids=new List<string>(); while(rd.Read())ids.Add(rd.GetString(0)); return ids; } }
    public void New(string id, string project) { lock(gate) { using var c=Open();using var tx=c.BeginTransaction();using var cmd=c.CreateCommand();cmd.Transaction=tx;cmd.CommandText="INSERT INTO jobs(id,project,status) VALUES($id,$p,'queued')";cmd.Parameters.AddWithValue("$id",id);cmd.Parameters.AddWithValue("$p",project);cmd.ExecuteNonQuery();AppendLifecycleAudit(c,tx,id,"-",0,"created",project);tx.Commit(); } }
    public JobInfo? Job(string id) { lock(gate) { using var c=Open(); using var cmd=c.CreateCommand(); cmd.CommandText="SELECT id,project,status,exit_code,error,image_digest,artifact_sha256 FROM jobs WHERE id=$id";cmd.Parameters.AddWithValue("$id",id);using var rd=cmd.ExecuteReader();return rd.Read()?new JobInfo(rd.GetString(0),rd.GetString(1),rd.GetString(2),rd.IsDBNull(3)?null:rd.GetInt32(3).ToString(),rd.IsDBNull(4)?null:rd.GetString(4),rd.IsDBNull(5)?null:rd.GetString(5),rd.IsDBNull(6)?null:rd.GetString(6)):null; } }
    public List<string[]> Records() { lock(gate) { using var c=Open();using var cmd=c.CreateCommand();cmd.CommandText="SELECT job_id,project_id,manifest_sha256,container_image_digest,started_at,finished_at,CAST(exit_code AS TEXT),artifact_sha256,previous_record_hash,record_hash FROM ledger ORDER BY seq";using var rd=cmd.ExecuteReader();var rows=new List<string[]>();while(rd.Read()){var row=new string[10];for(int i=0;i<10;i++)row[i]=rd.GetString(i);rows.Add(row);}return rows; } }
    public bool RecordCleanupEvidence(AttemptInfo a) { lock(gate) { using var c=Open();using var tx=c.BeginTransaction();using var cmd=c.CreateCommand();cmd.Transaction=tx;
        cmd.CommandText="SELECT 1 FROM jobs j JOIN attempts a ON a.job_id=j.id WHERE j.id=$id AND j.attempt_id=$aid AND j.attempt=$epoch AND j.status='running' AND a.attempt_id=$aid AND a.epoch=$epoch AND a.state='running'";
        cmd.Parameters.AddWithValue("$id",a.JobId);cmd.Parameters.AddWithValue("$aid",a.AttemptId);cmd.Parameters.AddWithValue("$epoch",a.Epoch);if(cmd.ExecuteScalar() is null)return false;
        cmd.CommandText="SELECT 1 FROM lifecycle_audit WHERE job_id=$id AND attempt_id=$aid AND epoch=$epoch AND event='cleanup_evidence'";
        if(cmd.ExecuteScalar() is not null)return false;
        AppendLifecycleAudit(c,tx,a.JobId,a.AttemptId,a.Epoch,"cleanup_evidence","cleanup observation recorded");tx.Commit();return true;
    } }
    public bool VerifyLifecycleAudit(){lock(gate){using var c=Open();using var cmd=c.CreateCommand();cmd.CommandText="SELECT seq,job_id,attempt_id,epoch,event,evidence,previous_hash,record_hash FROM lifecycle_audit ORDER BY seq";using var rd=cmd.ExecuteReader();long seq=0;var prev=new string('0',64);while(rd.Read()){
        if(rd.GetInt64(0)!=++seq)return false;
        var job=rd.GetString(1);var attempt=rd.GetString(2);var epoch=rd.GetInt64(3);var ev=rd.GetString(4);var evidence=rd.GetString(5);var previous=rd.GetString(6);var hash=rd.GetString(7);
        var initial=ev=="created"&&attempt=="-"&&epoch==0;
        if(string.IsNullOrWhiteSpace(job)||(!initial&&(!Guid.TryParseExact(attempt,"N",out _)||epoch<1))||string.IsNullOrWhiteSpace(ev)||string.IsNullOrWhiteSpace(evidence))return false;
        if(previous!=prev||Hash(string.Join("\n",new[]{job,attempt,epoch.ToString(CultureInfo.InvariantCulture),ev,evidence,previous}))!=hash)return false;prev=hash;
    }return true;}}
    public bool Verify() { var prev=new string('0',64);foreach(var row in Records()) {if(row[8]!=prev||Hash(string.Join("\n",row.Take(9)))!=row[9])return false;prev=row[9];}return true; }
    public bool VerifyRecoveryAudit(){lock(gate){using var c=Open();using var cmd=c.CreateCommand();cmd.CommandText="SELECT seq,job_id,attempt_id,epoch,decision,evidence,previous_hash,record_hash FROM recovery_audit ORDER BY seq";using var rd=cmd.ExecuteReader();long seq=0;var prev=new string('0',64);while(rd.Read()){
        if(rd.GetInt64(0)!=++seq)return false;
        var job=rd.GetString(1);var aid=rd.GetString(2);var epoch=rd.GetInt64(3);var decision=rd.GetString(4);var evidence=rd.GetString(5);var previous=rd.GetString(6);var hash=rd.GetString(7);
        if(string.IsNullOrWhiteSpace(job)||!Guid.TryParseExact(aid,"N",out _)||epoch<1||string.IsNullOrWhiteSpace(evidence)||!Enum.TryParse<RecoveryDecision>(decision,false,out var parsed)||parsed.ToString()!=decision)return false;
        if(previous!=prev||Hash(string.Join("\n",new[]{job,aid,epoch.ToString(CultureInfo.InvariantCulture),decision,evidence,previous}))!=hash)return false;prev=hash;
    }return true;}}
    private static void AppendLifecycleAudit(SqliteConnection c,SqliteTransaction tx,string job,string attempt,long epoch,string ev,string evidence) {
        using var cmd=c.CreateCommand();cmd.Transaction=tx;cmd.CommandText="SELECT record_hash FROM lifecycle_audit ORDER BY seq DESC LIMIT 1";var prev=(string?)cmd.ExecuteScalar()??new string('0',64);
        var hash=Hash(string.Join("\n",new[]{job,attempt,epoch.ToString(CultureInfo.InvariantCulture),ev,evidence,prev}));
        using var insert=c.CreateCommand();insert.Transaction=tx;insert.CommandText="INSERT INTO lifecycle_audit(job_id,attempt_id,epoch,event,evidence,previous_hash,record_hash) VALUES($job,$attempt,$epoch,$event,$evidence,$previous,$hash)";
        insert.Parameters.AddWithValue("$job",job);insert.Parameters.AddWithValue("$attempt",attempt);insert.Parameters.AddWithValue("$epoch",epoch);insert.Parameters.AddWithValue("$event",ev);insert.Parameters.AddWithValue("$evidence",evidence);insert.Parameters.AddWithValue("$previous",prev);insert.Parameters.AddWithValue("$hash",hash);
        if(insert.ExecuteNonQuery()!=1)throw new InvalidOperationException("Lifecycle audit insert failed");
    }
    public static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
}
sealed class Runner {
    private readonly string root,projects; private readonly Store db; private readonly Channel<string> queue;
    public Runner(string root,string projects,Store db,Channel<string> queue){this.root=root;this.projects=projects;this.db=db;this.queue=queue;}
    public async Task<string> Submit(string project,CancellationToken ct) {
        if(project.Length is < 1 or > 64 || !project.All(c=>char.IsAsciiLetterOrDigit(c)||c=='-'||c=='_'))throw new ArgumentException("Invalid project identifier");
        var src=Path.Combine(projects,project);if(!Directory.Exists(src))throw new ArgumentException("Unknown project");
        var manifest=ReadManifest(Path.Combine(src,"uer.json"));if(manifest.Project!=project)throw new ArgumentException("Project mismatch");
        var id=Guid.NewGuid().ToString("N");var target=Path.Combine(root,"jobs",id,"source");CopyTree(src,target);
        db.New(id,project);queue.Writer.TryWrite(id);return id;
    }
    public async Task<string> Replay(string id,CancellationToken ct){var job=db.Job(id)??throw new ArgumentException("Unknown job");if(job.Status is not ("passed" or "failed"))throw new InvalidOperationException("Job is not in a terminal state");var src=Path.Combine(root,"jobs",id,"source");var newid=Guid.NewGuid().ToString("N");CopyTree(src,Path.Combine(root,"jobs",newid,"source"));db.New(newid,job.Project);queue.Writer.TryWrite(newid);return newid;}
    static Manifest ReadManifest(string path){var m=JsonSerializer.Deserialize<Manifest>(File.ReadAllText(path),new JsonSerializerOptions{PropertyNameCaseInsensitive=true})??throw new ArgumentException("Empty manifest");if(m.Runtime is not ("python" or "node")||m.Operation!="test"||m.TimeoutSeconds is < 1 or > 300||m.MemoryMb is < 64 or > 2048||m.Cpu is < 1 or > 2)throw new ArgumentException("Disallowed manifest operation or limits");return m;}
    static void CopyTree(string src,string dest) {
      if((File.GetAttributes(src)&FileAttributes.ReparsePoint)!=0)throw new ArgumentException("Linked source directory rejected");
      var srcRoot=Path.GetFullPath(src); long total=0;int files=0;
      try {
        Directory.CreateDirectory(dest);
        var pending=new Stack<string>();pending.Push(srcRoot);
        while(pending.Count>0) {
          var dir=pending.Pop();
          if((File.GetAttributes(dir)&FileAttributes.ReparsePoint)!=0)throw new ArgumentException("Linked directory rejected");
          foreach(var entry in Directory.EnumerateFileSystemEntries(dir)) {
            var attr=File.GetAttributes(entry);
            if((attr&FileAttributes.ReparsePoint)!=0)throw new ArgumentException("Links not allowed");
            var rel=Path.GetRelativePath(srcRoot,entry);
            if(rel.StartsWith("..")||Path.IsPathRooted(rel))throw new ArgumentException("Invalid path");
            var target=Path.Combine(dest,rel);
            if((attr&FileAttributes.Directory)!=0) {Directory.CreateDirectory(target);pending.Push(entry);continue;}
            if(++files>500)throw new ArgumentException("Too many files");
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            // Open without following symbolic links where OS supports it; Linux O_NOFOLLOW
            // is not exposed by FileStream. This pre/post-check is not TOCTOU-proof.
            using var input=new FileStream(entry,FileMode.Open,FileAccess.Read,FileShare.Read,81920,FileOptions.SequentialScan);
            using var output=new FileStream(target,FileMode.CreateNew,FileAccess.Write,FileShare.None,81920);
            var buf=new byte[81920];int n;long perFile=0;
            while((n=input.Read(buf))>0) {
              perFile+=n;total+=n;
              if(perFile>5_000_000||total>20_000_000)throw new ArgumentException("Project exceeds byte limits");
              output.Write(buf,0,n);
            }
            if((File.GetAttributes(entry)&FileAttributes.ReparsePoint)!=0)throw new ArgumentException("Source changed during copy");
          }
        }
      } catch { if(Directory.Exists(dest))Directory.Delete(dest,true);throw; }
    }
    public static Task<(int,string)> DockerCommand(IEnumerable<string> args,int seconds,CancellationToken ct) => Exec("docker",args,seconds,ct);
    static async Task<(int,string)> Exec(string file,IEnumerable<string> args,int seconds,CancellationToken ct){using var p=new Process{StartInfo=new ProcessStartInfo(file){RedirectStandardError=true,RedirectStandardOutput=true,UseShellExecute=false,CreateNoWindow=true}};foreach(var a in args)p.StartInfo.ArgumentList.Add(a);p.Start();using var timer=CancellationTokenSource.CreateLinkedTokenSource(ct);timer.CancelAfter(TimeSpan.FromSeconds(seconds));// Drain pipes continuously with bounded retention to avoid unbounded memory.
        static async Task<string> Drain(StreamReader reader) { var buf=new char[4096]; var kept=new StringBuilder(); int n; while((n=await reader.ReadAsync(buf))>0) { if(kept.Length<500_000)kept.Append(buf,0,Math.Min(n,500_000-kept.Length)); } return kept.ToString(); }
        var stdout=Drain(p.StandardOutput);var stderr=Drain(p.StandardError);try{await p.WaitForExitAsync(timer.Token);}catch(OperationCanceledException) { try{p.Kill(entireProcessTree:true);}catch{} if(ct.IsCancellationRequested)throw;throw new TimeoutException("Process timeout"); }return(p.ExitCode,(await stdout)+(await stderr));}
    public async Task Execute(AttemptInfo attempt,CancellationToken ct){var id=attempt.JobId;var job=db.Job(id)!;var src=Path.Combine(root,"jobs",id,"source");var output=Path.Combine(root,"jobs",id,"output");Directory.CreateDirectory(output);var start=DateTimeOffset.UtcNow.ToString("O");var image="unresolved";var exit=-1;string? error=null;var manifestHash="missing";var artifact="missing";
      try{
        var path=Path.Combine(src,"uer.json");var m=ReadManifest(path);manifestHash=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        var tag=m.Runtime=="python"?Environment.GetEnvironmentVariable("UER_PYTHON_IMAGE"):Environment.GetEnvironmentVariable("UER_NODE_IMAGE");
        if(string.IsNullOrWhiteSpace(tag) || !System.Text.RegularExpressions.Regex.IsMatch(tag, @"^[a-zA-Z0-9./_-]+@sha256:[0-9a-f]{64}$"))throw new InvalidOperationException("Set pinned UER_PYTHON_IMAGE / UER_NODE_IMAGE to repository@sha256:<64 hex>");
        var inspected=await Exec("docker",["image","inspect","--format","{{json .RepoDigests}}",tag],20,ct);
        if(inspected.Item1!=0)throw new InvalidOperationException("Image unavailable: pull "+tag);
        image=tag;
        var name=attempt.ContainerName;var command=m.Runtime=="python"?new[]{"python","-m","unittest","discover","-s","tests","-v"}:new[]{"node","--test"};
        var args=new List<string>{"create","--name",name,"--label","blackwolf.uer=true","--label","blackwolf.job_id="+id,"--label","blackwolf.attempt_id="+attempt.AttemptId,"--label","blackwolf.execution_epoch="+attempt.Epoch.ToString(CultureInfo.InvariantCulture),"--network","none","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges","--pids-limit","64","--memory",m.MemoryMb+"m","--cpus",m.Cpu.ToString(System.Globalization.CultureInfo.InvariantCulture),"--tmpfs","/tmp:rw,noexec,nosuid,size=32m","--user","65534:65534","--mount",$"type=bind,source={src},target=/work,readonly","--env","PYTHONPATH=/work","--workdir","/work",image};args.AddRange(command);
        try {
          var created=await Exec("docker",args,30,ct);
          if(created.Item1!=0)throw new InvalidOperationException("Docker create failed or uncertain: "+created.Item2);
          if(!db.MarkContainerCreated(attempt))throw new InvalidOperationException("Container-created transition rejected");
          // docker start returning does not mean the SQLite RUNNING transition has committed.
          // A crash in that gap is recovered fail-closed using the precommitted container name.
          var started=await Exec("docker",["start",name],30,ct);
          if(started.Item1!=0)throw new InvalidOperationException("Docker start failed or uncertain: "+started.Item2);
          if(!db.MarkRunning(attempt))throw new InvalidOperationException("Running transition rejected");
          var waited=await Exec("docker",["wait",name],m.TimeoutSeconds,ct);
          if(waited.Item1!=0||!int.TryParse(waited.Item2.Trim(),out exit))throw new InvalidOperationException("Docker wait result unverified: "+waited.Item2);
          var logs=await Exec("docker",["logs",name],20,ct);
          if(logs.Item1!=0)throw new InvalidOperationException("Docker logs unavailable: "+logs.Item2);
          File.WriteAllText(Path.Combine(output,"test.log"),logs.Item2.Length>1_000_000?logs.Item2[..1_000_000]:logs.Item2);
        }
        catch(OperationCanceledException) when(ct.IsCancellationRequested){throw;}
        finally {
          try { var cleanup=await Exec("docker",["rm","-f",name],15,CancellationToken.None);if(cleanup.Item1!=0)throw new InvalidOperationException("Docker cleanup returned nonzero");
            var verify=await Exec("docker",["ps","-a","--filter","name=^/"+name+"$","--format","{{.Names}}"],15,CancellationToken.None);
            if(verify.Item1!=0||verify.Item2.Split('\n',StringSplitOptions.RemoveEmptyEntries).Any(x=>x.Trim()==name))throw new InvalidOperationException("Container absence not confirmed");
          }catch(Exception ex){db.Quarantine(attempt,"Container cleanup unverified: "+ex.Message);throw;}
        }
        artifact=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Path.Combine(output,"test.log")))).ToLowerInvariant();
      }catch(OperationCanceledException) when(ct.IsCancellationRequested){db.Quarantine(attempt,"Service shutdown interrupted attempt; reconciliation required");throw;}catch(Exception ex){error=ex.Message;File.WriteAllText(Path.Combine(output,"error.txt"),error);artifact=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Path.Combine(output,"error.txt")))).ToLowerInvariant();}
      var finish=DateTimeOffset.UtcNow.ToString("O");if(!db.Complete(attempt,job.Project,manifestHash,image,start,finish,exit,artifact,error))Console.Error.WriteLine($"Stale result rejected: {attempt.AttemptId}");
    }
}
sealed class Worker : BackgroundService {
 private readonly Runner runner;private readonly Store db;
 public Worker(Runner runner,Store db){this.runner=runner;this.db=db;}
 // Only a single UER process may own this SQLite database in v0.1.1.
 protected override async Task ExecuteAsync(CancellationToken stoppingToken) {
  foreach(var a in db.InterruptedAttempts()) {
   if(stoppingToken.IsCancellationRequested)return;
   try {
    // Docker errors must never be interpreted as absence of a container.
    var check=await Runner.DockerCommand(["ps","-a","--filter","label=blackwolf.attempt_id="+a.AttemptId,"--format","{{.ID}} {{.Names}}"],20,stoppingToken);
    if(check.Item1!=0)throw new InvalidOperationException("Docker enumeration failed");
    var rows=check.Item2.Split('\n',StringSplitOptions.RemoveEmptyEntries);
    if(rows.Any(row=>!row.Trim().EndsWith(" "+a.ContainerName,StringComparison.Ordinal)))throw new InvalidOperationException("Container identity mismatch");
    // Also inspect the preselected name: a crash can occur before labels become visible.
    var named=await Runner.DockerCommand(["ps","-a","--filter","name=^/"+a.ContainerName+"$","--format","{{.Names}}"],20,stoppingToken);
    if(named.Item1!=0)throw new InvalidOperationException("Docker name lookup failed");
    if(rows.Length>0||named.Item2.Split('\n',StringSplitOptions.RemoveEmptyEntries).Any(x=>x.Trim()==a.ContainerName)) {
      var removed=await Runner.DockerCommand(["rm","-f",a.ContainerName],20,stoppingToken);
      if(removed.Item1!=0)throw new InvalidOperationException("Orphan removal failed");
    }
    var verify=await Runner.DockerCommand(["ps","-a","--filter","name=^/"+a.ContainerName+"$","--format","{{.Names}}"],20,stoppingToken);
    if(verify.Item1!=0||verify.Item2.Split('\n',StringSplitOptions.RemoveEmptyEntries).Any(x=>x.Trim()==a.ContainerName))throw new InvalidOperationException("Termination not confirmed");
    // Absence of a container proves neither non-execution nor absence of external effects.
    // No trusted completion receipt or retry-safety attestation exists in v0.1.1.
    // Therefore this recovery path MUST fail closed even after verified container removal.
    var decision=RecoveryPolicy.EvaluateRecovery(previousExecutionTerminated:true,retrySafetyProven:false,completionVerified:false);
    if(!db.Reconcile(a,decision,"Recovery: container no longer visible; execution effects remain unverified"))
      throw new InvalidOperationException("Recovery transition rejected by fencing");
   }catch(OperationCanceledException) when(stoppingToken.IsCancellationRequested){return;}
    catch(Exception e){db.Quarantine(a,"Recovery blocked: "+e.Message);Console.Error.WriteLine($"Quarantined {a.JobId}: {e.Message}");}
  }
  while(!stoppingToken.IsCancellationRequested){
   foreach(var id in db.Pending()){
    if(stoppingToken.IsCancellationRequested)break;
    var attempt=db.TryClaim(id);if(attempt is null)continue;
    try{await runner.Execute(attempt,stoppingToken);}
    catch(OperationCanceledException) when(stoppingToken.IsCancellationRequested){return;}
    catch(Exception e){db.Quarantine(attempt,"Unexpected worker error: "+e.Message);}
   }
   try{await Task.Delay(500,stoppingToken);}catch(OperationCanceledException){break;}
  }
 }
}
