using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using K92N.Core;
using Microsoft.Data.Sqlite;

var tests=new (string Name,Action<Fixture> Run)[]{
 ("Balanced post and audit",f=>{f.Post();True(f.Store.VerifyIntegrity().IsValid);}),
 ("Unbalanced fails and rolls back",f=>{Throws(()=>f.Store.PostEntry(f.Req(100,99)));Equal(0L,f.Store.VerifyIntegrity().EntriesChecked);}),
 ("Negative rejected",f=>Throws(()=>f.Store.PostEntry(f.Req(-1,-1)))),
 ("Precision rejected",f=>Throws(()=>f.Store.PostEntry(f.Req(1.001m,1.001m)))),
 ("Foreign currency precision",f=>{f.Store.PostEntry(f.Req(3.25m,3.25m) with{Lines=[new(1,"KWD",1.000m,0,3.25m,0),new(2,"USD",0,3.25m,0,3.25m)]});True(f.Store.VerifyIntegrity().IsValid);}),
 ("Idempotent retry",f=>{var a=f.Post("same");Equal(a,f.Post("same"));Equal(1L,f.Store.VerifyIntegrity().EntriesChecked);}),
 ("Idempotency conflict",f=>{f.Post("same");Throws(()=>f.Store.PostEntry(f.Req(101,101,"same")));}),
 ("Positive mirror reversal",f=>{var id=f.Post();f.Store.ReverseEntry(id,new(2026,11,9),"return","r1");var v=f.Store.VerifyIntegrity();True(v.IsValid,v.Problem);Equal(2L,v.EntriesChecked);}),
 ("Reversal retry",f=>{var id=f.Post();Equal(f.Store.ReverseEntry(id,new(2026,11,9),"return","r1"),f.Store.ReverseEntry(id,new(2026,11,9),"return","r1"));}),
 ("Second reversal blocked",f=>{var id=f.Post();f.Store.ReverseEntry(id,new(2026,11,9),"first");Throws(()=>f.Store.ReverseEntry(id,new(2026,11,9),"second"));}),
 ("Period lock",f=>{f.Store.LockPeriod(new(2026,11,8));Throws(()=>f.Post());}),
 ("Separated balances",f=>{f.Store.PostEntry(f.Req(10,10) with{Lines=[new(1,"USD",10,0,10,0,5),new(2,"USD",0,10,0,10)]});var b=f.Store.CustomerBalances(5,1);Equal(1000L,b["USD"]);True(!b.ContainsKey("TRY"));}),
 ("Hash encoding known vector",f=>{_ = f;Equal("e69def7e30098762a1c0405c820449abd969446fb9a09640f0f655a20ae30b5c",Store.CanonHash(2,"كريم",null,100));}),
 ("Fabricated reversal with real hashes rejected by verifier",f=>{var id=f.Post();f.FabricateReversal(id);var r=f.Store.VerifyIntegrity();True(!r.IsValid);Equal("REVERSAL_MIRROR_MISMATCH",r.Problem);}),
 ("Legacy-shaped huge line number does not crash",f=>{f.Post();f.Raw("PRAGMA ignore_check_constraints=ON;DROP TRIGGER journal_lines_no_update;UPDATE journal_lines SET line_no=3000000000 WHERE entry_id=1 AND line_no=2;");var v=f.Store.VerifyIntegrity();True(!v.IsValid);Equal("LINE_NUMBERS_NOT_SEQUENTIAL",v.Problem);}),
 ("Malformed stored date rejected even with correct hashes",f=>{f.Post();f.Raw("PRAGMA ignore_check_constraints=ON;DROP TRIGGER journal_entries_no_update;UPDATE journal_entries SET entry_date='2026-13-45' WHERE id=1;");Equal("DATE_INVALID",f.Store.VerifyIntegrity().Problem);}),
 ("External anchor detects truncation",f=>{f.Post();True(!f.Store.VerifyIntegrity(new string('1',64)).IsValid);}),
 ("Replay deterministic and no verified claim",f=>{using var doc=JsonDocument.Parse("{\"text\":\"decision\",\"status\":\"RECORDED\"}");f.Store.Record("decision","ADR-X",doc.RootElement);var a=f.Store.Replay();var b=f.Store.Replay();True(a.IsValid);Equal(JsonSerializer.Serialize(a),JsonSerializer.Serialize(b));using var bad=JsonDocument.Parse("{\"status\":\"VERIFIED\"}");Throws(()=>f.Store.Record("evidence","e",bad.RootElement));}),
 ("Concurrent unique requests",f=>{Parallel.For(0,16,i=>f.Store.PostEntry(f.Req(1,1,"c-"+i)));var r=f.Store.VerifyIntegrity();True(r.IsValid,r.Problem);Equal(16L,r.EntriesChecked);})
};
using(var probe=new SqliteConnection("Data Source=:memory:")){probe.Open();Console.WriteLine("SQLITE_NATIVE_VERSION="+probe.ServerVersion);if(Version.Parse(probe.ServerVersion)<new Version(3,50,2))throw new Exception("Native SQLite is below security baseline 3.50.2");}
var failed=0;
foreach(var test in tests){using var f=new Fixture();try{test.Run(f);Console.WriteLine("PASS "+test.Name);}catch(Exception e){failed++;Console.Error.WriteLine("FAIL "+test.Name+": "+e);}}
Console.WriteLine($"Executed {tests.Length}; failures {failed}");return failed==0?0:1;
static void True(bool b,string? reason=null){if(!b)throw new Exception(reason??"Assertion failed");}
static void Equal<T>(T a,T b){if(!EqualityComparer<T>.Default.Equals(a,b))throw new Exception($"Expected {a}, observed {b}");}
static void Throws(Action a){try{a();}catch(LedgerException){return;}throw new Exception("Expected LedgerException");}
sealed class Fixture:IDisposable
{
 public readonly string Dir=Path.Combine(Path.GetTempPath(),"k92n-test-"+Guid.NewGuid().ToString("N"));
 public string PathDb=>Path.Combine(Dir,"test.db");public Store Store{get;}
 public Fixture(){Directory.CreateDirectory(Dir);Store=new(new(PathDb));Store.CreateAccount(1,"1000","Cash");Store.CreateAccount(2,"1200","Receivables");}
 public PostEntryRequest Req(decimal d=100,decimal c=100,string? key=null)=>new(new(2026,11,8),"test","USD",null,"INVOICE",null,[new(1,"USD",d,0,d,0),new(2,"USD",0,c,0,c)],key);
 public long Post(string? key=null)=>Store.PostEntry(Req(key:key));
 public void Raw(string sql){using var db=new SqliteConnection(new SqliteConnectionStringBuilder{DataSource=PathDb,ForeignKeys=true,Pooling=false}.ToString());db.Open();using var q=db.CreateCommand();q.CommandText="PRAGMA recursive_triggers=ON;"+sql;q.ExecuteNonQuery();}
 public void FabricateReversal(long original)
 {
  using var db=new SqliteConnection($"Data Source={PathDb};Pooling=False");db.Open();
  using var head=db.CreateCommand();head.CommandText="SELECT entry_hash FROM journal_entries ORDER BY id DESC LIMIT 1";var prev=(string)head.ExecuteScalar()!;
  const string at="2026-11-09T00:00:00.000Z";
  // Independent test encoder, no production hash-helper calls.
  var fp=TestHash(2,"2026-11-09","fake","USD",null,"REVERSAL",null,original,2,
    1,1,"USD",0,5000,0,5000,null,null,2,2,"USD",5000,0,5000,0,null,null);
  var hash=TestHash(2,prev,at,null,fp);
  using var q=db.CreateCommand();q.CommandText="""
   BEGIN IMMEDIATE;
   DROP TRIGGER seal_guard;
   INSERT INTO journal_entries(entry_date,description,currency_code,reference,entry_type,created_by,idempotency_key,reverses_entry_id,line_count,total_base,posted_at,hash_version,fingerprint,prev_hash,entry_hash)
   VALUES('2026-11-09','fake','USD',NULL,'REVERSAL',NULL,NULL,$orig,2,5000,$at,2,$fp,$prev,$hash);
   INSERT INTO journal_lines VALUES(2,1,1,'USD',0,5000,0,5000,NULL,NULL),(2,2,2,'USD',5000,0,5000,0,NULL,NULL);
   INSERT INTO journal_seals VALUES(2,$at);
   COMMIT;
   """;
  q.Parameters.AddWithValue("$orig",original);q.Parameters.AddWithValue("$at",at);q.Parameters.AddWithValue("$fp",fp);q.Parameters.AddWithValue("$prev",prev);q.Parameters.AddWithValue("$hash",hash);q.ExecuteNonQuery();
 }
 static string TestHash(params object?[] fields){var text=new StringBuilder();foreach(var f in fields){if(f is null){text.Append("-1:");continue;}var s=Convert.ToString(f,CultureInfo.InvariantCulture)!;text.Append(Encoding.UTF8.GetByteCount(s).ToString(CultureInfo.InvariantCulture)).Append(':').Append(s);}return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text.ToString())));}
 public void Dispose(){SqliteConnection.ClearAllPools();Directory.Delete(Dir,true);}
}
