using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;

namespace K92N.Core;

public sealed record JournalLineDto(long AccountId,string CurrencyCode,decimal DebitOrig,decimal CreditOrig,decimal DebitBase,decimal CreditBase,long? CustomerId=null,long? InvoiceId=null);
public sealed record PostEntryRequest(DateOnly EntryDate,string Description,string CurrencyCode,string? Reference,string EntryType,long? CreatedBy,IReadOnlyList<JournalLineDto> Lines,string? IdempotencyKey=null);
public sealed record IntegrityReport(bool IsValid,long EntriesChecked,string HeadHash,long? FirstBadEntryId,string? Problem);
public sealed record LedgerOptions(string DbPath,int BusyTimeoutMs=5000);
public sealed class LedgerException(string code,string message,Exception? inner=null):Exception(message,inner){public string Code{get;}=code;}
public sealed record StoredLine(long LineNo,long AccountId,string Currency,long DebitOrig,long CreditOrig,long DebitBase,long CreditBase,long? CustomerId,long? InvoiceId);
public sealed record StoredEntry(long Id,string Date,string Description,string Currency,string? Reference,string Type,long? CreatedBy,string? IdempotencyKey,long? ReversesId,long LineCount,long Total,string At,long HashVersion,string Fingerprint,string PrevHash,string Hash);
public sealed record GovernanceEvent(long Seq,string At,string Kind,string EntityId,string Payload,string PrevHash,string Hash);
public sealed record ReplayReport(bool IsValid,long EventsChecked,string HeadHash,string? Problem,SortedDictionary<string,JsonElement> Projection);

// New reconstruction; not a byte-for-byte recovery of Sovereign Core v2.
public sealed class Store
{
 public const string Genesis="0000000000000000000000000000000000000000000000000000000000000000";
 public const long MaxMinor=1_000_000_000_000_000;
 public const int MaxLines=1000;
 readonly string connectionString; readonly int busyMs;
 readonly Dictionary<string,int> currencies=new(StringComparer.Ordinal);
 public Store(LedgerOptions options)
 {
  if(string.IsNullOrWhiteSpace(options.DbPath))throw Error("CONFIG","DB path required");
  if(options.BusyTimeoutMs<0||options.BusyTimeoutMs>300000)throw Error("CONFIG","Busy timeout outside 0..300000 ms");
  busyMs=options.BusyTimeoutMs;
  var path=Path.GetFullPath(options.DbPath);Directory.CreateDirectory(Path.GetDirectoryName(path)!);
  connectionString=new SqliteConnectionStringBuilder{DataSource=path,ForeignKeys=true,DefaultTimeout=Math.Max(1,(int)Math.Ceiling(busyMs/1000d)),Pooling=false}.ToString();
  Write(c=>{
   var tables=Convert.ToInt64(Scalar(c,"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"),CultureInfo.InvariantCulture);
   if(tables==0){using var stream=typeof(Store).Assembly.GetManifestResourceStream("K92N.Core.schema.sql")??throw Error("CONFIG","Schema missing");using var reader=new StreamReader(stream);Exec(c,reader.ReadToEnd());}
   else if(Convert.ToInt64(Scalar(c,"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='system_meta'"),CultureInfo.InvariantCulture)!=1 || (Scalar(c,"SELECT value FROM system_meta WHERE key='schema_version'") as string)!="1" || (Scalar(c,"SELECT value FROM system_meta WHERE key='hash_contract'") as string)!="2")
    throw Error("MIGRATION_REQUIRED","Existing database is not the reconstructed schema; no automatic upgrade");
   if((Scalar(c,"SELECT value FROM ledger_meta WHERE key='base_currency'") as string)!="USD")throw Error("CONFIG","Base currency must be USD for this schema");
   using var cmd=Command(c,"SELECT code,minor_units FROM currencies");using var r=cmd.ExecuteReader();while(r.Read()){var n=r.GetInt64(1);if(n<0||n>6)throw Error("CONFIG","Invalid currency precision");currencies.Add(r.GetString(0),(int)n);}return 0;
  });
  using(var c=Open())Exec(c,"PRAGMA journal_mode=WAL;");
 }
 static LedgerException Error(string code,string message)=>new(code,message);
 SqliteConnection Open(){var c=new SqliteConnection(connectionString);try{c.Open();Exec(c,$"PRAGMA foreign_keys=ON;PRAGMA recursive_triggers=ON;PRAGMA synchronous=FULL;PRAGMA busy_timeout={busyMs};");return c;}catch{c.Dispose();throw;}}
 static SqliteCommand Command(SqliteConnection c,string sql,params (string Name,object? Value)[] args){var q=c.CreateCommand();q.CommandText=sql;foreach(var a in args)q.Parameters.AddWithValue(a.Name,a.Value??DBNull.Value);return q;}
 static object? Scalar(SqliteConnection c,string sql,params (string Name,object? Value)[] args){using var q=Command(c,sql,args);return q.ExecuteScalar();}
 static void Exec(SqliteConnection c,string sql,params (string Name,object? Value)[] args){using var q=Command(c,sql,args);q.ExecuteNonQuery();}
 T Write<T>(Func<SqliteConnection,T> work){try{using var c=Open();Exec(c,"BEGIN IMMEDIATE");try{var result=work(c);Exec(c,"COMMIT");return result;}catch{try{Exec(c,"ROLLBACK");}catch(SqliteException){}throw;}}catch(SqliteException e){throw new LedgerException(e.SqliteErrorCode is 5 or 6?"BUSY":"STORAGE_REJECTED",e.Message,e);}}
 static string At()=>DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'",CultureInfo.InvariantCulture);
 static string Iso(DateOnly d)=>d.ToString("yyyy-MM-dd",CultureInfo.InvariantCulture);
 static void Text(string? v,int max,string field,bool required=false){if((required&&string.IsNullOrWhiteSpace(v))||v?.Length>max||v?.Contains('\0')==true)throw Error("INVALID_REQUEST",field);if(v is not null){try{_ =new UTF8Encoding(false,true).GetBytes(v);}catch(EncoderFallbackException){throw Error("INVALID_REQUEST",field+" invalid Unicode");}}}
 static void Key(string? v){Text(v,100,"idempotency_key");if(v is not null&&string.IsNullOrWhiteSpace(v))throw Error("INVALID_REQUEST","Blank idempotency key");}
 public void CreateAccount(long id,string code,string name){if(id<=0)throw Error("INVALID_REQUEST","Account id");Text(code,40,"code",true);Text(name,120,"name",true);Write(c=>{Exec(c,"INSERT INTO accounts VALUES($i,$c,$n)",("$i",id),("$c",code),("$n",name));return 0;});}
 long Minor(decimal amount,string? currency){if(currency is null)throw Error("UNKNOWN_CURRENCY","Currency is required");if(!currencies.TryGetValue(currency,out var digits))throw Error("UNKNOWN_CURRENCY",currency);decimal scale=1;for(var i=0;i<digits;i++)scale*=10;if(amount<0)throw Error("NEGATIVE_AMOUNT","Negative amount");if(amount>MaxMinor/scale)throw Error("AMOUNT_OVERFLOW","Amount exceeds limit");var n=amount*scale;if(n!=decimal.Truncate(n))throw Error("PRECISION_VIOLATION","No silent rounding");return (long)n;}
 StoredLine ConvertLine(JournalLineDto l,long no){if(l.AccountId<=0||l.CustomerId is <=0||l.InvoiceId is <=0)throw Error("INVALID_LINE","Identifiers must be positive");return new(no,l.AccountId,l.CurrencyCode,Minor(l.DebitOrig,l.CurrencyCode),Minor(l.CreditOrig,l.CurrencyCode),Minor(l.DebitBase,"USD"),Minor(l.CreditBase,"USD"),l.CustomerId,l.InvoiceId);}
 string? LineProblem(StoredLine l,long expected){if(l.LineNo!=expected||l.LineNo<1||l.LineNo>MaxLines)return "LINE_NUMBERS_NOT_SEQUENTIAL";if(l.AccountId<=0||l.CustomerId is <=0||l.InvoiceId is <=0)return "LINE_IDENTIFIER_INVALID";if(!currencies.ContainsKey(l.Currency))return "UNKNOWN_CURRENCY";if(new[]{l.DebitOrig,l.CreditOrig,l.DebitBase,l.CreditBase}.Any(n=>n<0||n>MaxMinor))return "AMOUNT_OUT_OF_RANGE";if(!((l.DebitOrig>0&&l.DebitBase>0&&l.CreditOrig==0&&l.CreditBase==0)||(l.CreditOrig>0&&l.CreditBase>0&&l.DebitOrig==0&&l.DebitBase==0)))return "LINE_SIDE_INVALID";if(l.Currency=="USD"&&(l.DebitOrig!=l.DebitBase||l.CreditOrig!=l.CreditBase))return "BASE_AMOUNT_MISMATCH";return null;}
 static long Sum(IReadOnlyList<StoredLine> lines,bool debit){long sum=0;try{checked{foreach(var l in lines)sum+=debit?l.DebitBase:l.CreditBase;}}catch(OverflowException){throw Error("AMOUNT_OVERFLOW","Total overflow");}return sum;}
 public long PostEntry(PostEntryRequest req)
 {
  ArgumentNullException.ThrowIfNull(req);Text(req.Description,500,"description",true);Text(req.Reference,100,"reference");Key(req.IdempotencyKey);
  var headerCurrency=req.CurrencyCode??throw Error("INVALID_REQUEST","Header currency is required");
  if(req.CreatedBy is <=0||!currencies.ContainsKey(headerCurrency))throw Error("INVALID_REQUEST","Header identifiers/currency");
  if(!ValidType(req.EntryType)||req.EntryType=="REVERSAL")throw Error("INVALID_REQUEST","Entry type; REVERSAL is reserved");
  var src=req.Lines?.ToArray()??throw Error("INVALID_REQUEST","Lines required");if(src.Length<2||src.Length>MaxLines)throw Error("INVALID_REQUEST","2..1000 lines required");
  var lines=src.Select((l,i)=>ConvertLine(l??throw Error("INVALID_LINE","Null line"),i+1)).ToArray();
  for(var i=0;i<lines.Length;i++){var p=LineProblem(lines[i],i+1);if(p is not null)throw Error("INVALID_LINE",p);}
  var total=Sum(lines,true);if(total<=0||total!=Sum(lines,false))throw Error("UNBALANCED_ENTRY","Debits must equal credits and be positive");
  return Write(c=>Insert(c,new(0,Iso(req.EntryDate),req.Description,headerCurrency,req.Reference,req.EntryType,req.CreatedBy,req.IdempotencyKey,null,lines.Length,total,"",2,"","",""),lines));
 }
 public long ReverseEntry(long entryId,DateOnly date,string reason,string? key=null)
 {
  if(entryId<=0)throw Error("INVALID_REQUEST","Entry id");Text(reason,300,"reason",true);Key(key);
  return Write(c=>{var original=Headers(c,entryId).SingleOrDefault()??throw Error("ENTRY_NOT_FOUND","Entry not found");var lines=Lines(c,entryId);
   var why=Check(c,original,lines,original.PrevHash);if(why is not null)throw Error("INTEGRITY_VIOLATION",why);
   var mirrored=lines.Select(l=>l with{DebitOrig=l.CreditOrig,CreditOrig=l.DebitOrig,DebitBase=l.CreditBase,CreditBase=l.DebitBase}).ToArray();
   return Insert(c,new(0,Iso(date),$"REVERSAL of #{entryId}: {reason}",original.Currency,original.Reference,"REVERSAL",null,key,entryId,mirrored.Length,original.Total,"",2,"","",""),mirrored);
  });
 }
 long Insert(SqliteConnection c,StoredEntry h,IReadOnlyList<StoredLine> lines)
 {
  var fp=Fingerprint(h,lines);
  if(h.IdempotencyKey is not null){using var q=Command(c,"SELECT id,fingerprint FROM journal_entries WHERE idempotency_key=$k",("$k",h.IdempotencyKey));using var r=q.ExecuteReader();if(r.Read()){if(r.GetString(1)!=fp)throw Error("IDEMPOTENCY_CONFLICT","Key reused with different content");if(Scalar(c,"SELECT entry_id FROM journal_seals WHERE entry_id=$i",("$i",r.GetInt64(0))) is null)throw Error("INTEGRITY_VIOLATION","Idempotent entry unsealed");return r.GetInt64(0);}}
  var prev=Scalar(c,"SELECT entry_hash FROM journal_entries ORDER BY id DESC LIMIT 1") as string??Genesis;var at=At();var hash=EntryHash(prev,at,h.IdempotencyKey,fp);
  var result=Scalar(c,"""
   INSERT INTO journal_entries(entry_date,description,currency_code,reference,entry_type,created_by,idempotency_key,reverses_entry_id,line_count,total_base,posted_at,hash_version,fingerprint,prev_hash,entry_hash)
   VALUES($d,$desc,$cur,$ref,$t,$by,$k,$rev,$n,$tot,$at,2,$fp,$prev,$hash) RETURNING id
   """,("$d",h.Date),("$desc",h.Description),("$cur",h.Currency),("$ref",h.Reference),("$t",h.Type),("$by",h.CreatedBy),("$k",h.IdempotencyKey),("$rev",h.ReversesId),("$n",lines.Count),("$tot",h.Total),("$at",at),("$fp",fp),("$prev",prev),("$hash",hash));
  if(result is not long id||id<=0)throw Error("STORAGE_REJECTED","Missing inserted id");
  foreach(var l in lines)Exec(c,"INSERT INTO journal_lines VALUES($e,$n,$a,$c,$do,$co,$db,$cb,$cu,$in)",("$e",id),("$n",l.LineNo),("$a",l.AccountId),("$c",l.Currency),("$do",l.DebitOrig),("$co",l.CreditOrig),("$db",l.DebitBase),("$cb",l.CreditBase),("$cu",l.CustomerId),("$in",l.InvoiceId));
  // This explicit seal is inserted AFTER lines, within the same transaction.
  Exec(c,"INSERT INTO journal_seals VALUES($i,$at)",("$i",id),("$at",at));
  return id;
 }
 public long LockPeriod(DateOnly through)=>Write(c=>{var r=Scalar(c,"INSERT INTO period_locks(locked_through,locked_at) VALUES($d,$at) RETURNING id",("$d",Iso(through)),("$at",At()));return r is long n?n:throw Error("STORAGE_REJECTED","Missing lock id");});
 public Dictionary<string,long> CustomerBalances(long customerId,long accountId){if(customerId<=0||accountId<=0)throw Error("INVALID_REQUEST","Positive customer and control account required");using var c=Open();using var q=Command(c,"SELECT currency_code,SUM(debit_orig-credit_orig) FROM posted_lines WHERE customer_id=$c AND account_id=$a GROUP BY currency_code",("$c",customerId),("$a",accountId));using var r=q.ExecuteReader();var result=new Dictionary<string,long>();while(r.Read())result[r.GetString(0)]=r.GetInt64(1);return result;}
 static long? N(SqliteDataReader r,int i)=>r.IsDBNull(i)?null:r.GetInt64(i);static string? S(SqliteDataReader r,int i)=>r.IsDBNull(i)?null:r.GetString(i);
 static List<StoredEntry> Headers(SqliteConnection c,long? id=null){using var q=Command(c,"SELECT id,entry_date,description,currency_code,reference,entry_type,created_by,idempotency_key,reverses_entry_id,line_count,total_base,posted_at,hash_version,fingerprint,prev_hash,entry_hash FROM journal_entries WHERE ($id IS NULL OR id=$id) ORDER BY id",("$id",id));using var r=q.ExecuteReader();var a=new List<StoredEntry>();while(r.Read())a.Add(new(r.GetInt64(0),r.GetString(1),r.GetString(2),r.GetString(3),S(r,4),r.GetString(5),N(r,6),S(r,7),N(r,8),r.GetInt64(9),r.GetInt64(10),r.GetString(11),r.GetInt64(12),r.GetString(13),r.GetString(14),r.GetString(15)));return a;}
 static List<StoredLine> Lines(SqliteConnection c,long id){using var q=Command(c,"SELECT line_no,account_id,currency_code,debit_orig,credit_orig,debit_base,credit_base,customer_id,invoice_id FROM journal_lines WHERE entry_id=$i ORDER BY line_no",("$i",id));using var r=q.ExecuteReader();var a=new List<StoredLine>();while(r.Read()){if(a.Count>=MaxLines)throw Error("INTEGRITY_VIOLATION","Too many stored lines");a.Add(new(r.GetInt64(0),r.GetInt64(1),r.GetString(2),r.GetInt64(3),r.GetInt64(4),r.GetInt64(5),r.GetInt64(6),N(r,7),N(r,8)));}return a;}
 static bool ValidType(string? s)=>s is {Length:>=2 and <=32}&&s.All(c=>c is >= 'A' and <= 'Z' or >= '0' and <= '9' or '_');
 string? Check(SqliteConnection c,StoredEntry h,IReadOnlyList<StoredLine> lines,string prev)
 {
  if(h.HashVersion!=2)return "HASH_VERSION_UNSUPPORTED";
  if(h.Id<=0||h.CreatedBy is <=0||h.LineCount<2||h.LineCount>MaxLines||h.Total<=0||h.Total>1_000_000_000_000_000_000)return "HEADER_RANGE_INVALID";
  if(!DateOnly.TryParseExact(h.Date,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out _)||!DateTimeOffset.TryParseExact(h.At,"yyyy-MM-dd'T'HH:mm:ss.fff'Z'",CultureInfo.InvariantCulture,DateTimeStyles.AssumeUniversal,out _))return "DATE_INVALID";
  try{Text(h.Description,500,"description",true);Text(h.Reference,100,"reference");Key(h.IdempotencyKey);}catch(LedgerException){return "HEADER_TEXT_INVALID";}
  if(!ValidType(h.Type)||!currencies.ContainsKey(h.Currency))return "HEADER_TYPE_OR_CURRENCY_INVALID";
  if((h.Type=="REVERSAL")!=h.ReversesId.HasValue)return "REVERSAL_TAG_MISMATCH";
  if(h.PrevHash!=prev)return "CHAIN_LINK_BROKEN";
  if(lines.Count!=h.LineCount)return "LINE_COUNT_MISMATCH";
  for(var i=0;i<lines.Count;i++){var p=LineProblem(lines[i],i+1);if(p is not null)return p;if(Scalar(c,"SELECT id FROM accounts WHERE id=$i",("$i",lines[i].AccountId)) is null)return "ACCOUNT_NOT_FOUND";}
  if(Sum(lines,true)!=h.Total||Sum(lines,false)!=h.Total)return "TOTALS_MISMATCH";
  if(Fingerprint(h,lines)!=h.Fingerprint)return "CONTENT_HASH_MISMATCH";
  if(EntryHash(h.PrevHash,h.At,h.IdempotencyKey,h.Fingerprint)!=h.Hash)return "ENTRY_HASH_MISMATCH";
  if(Scalar(c,"SELECT entry_id FROM journal_seals WHERE entry_id=$i",("$i",h.Id)) is null)return "ENTRY_UNSEALED";
  if(h.ReversesId is long target){if(target>=h.Id||target<=0)return "REVERSAL_TARGET_INVALID";var original=Headers(c,target).SingleOrDefault();if(original is null)return "REVERSAL_TARGET_NOT_FOUND";if(Scalar(c,"SELECT entry_id FROM journal_seals WHERE entry_id=$i",("$i",target)) is null)return "REVERSAL_TARGET_UNSEALED";if(original.Currency!=h.Currency||original.Reference!=h.Reference||original.LineCount!=h.LineCount)return "REVERSAL_HEADER_MISMATCH";var o=Lines(c,target);if(o.Count!=lines.Count)return "REVERSAL_LINE_COUNT_MISMATCH";for(var i=0;i<o.Count;i++){var a=lines[i];var b=o[i];if(a!=(b with{DebitOrig=b.CreditOrig,CreditOrig=b.DebitOrig,DebitBase=b.CreditBase,CreditBase=b.DebitBase}))return "REVERSAL_MIRROR_MISMATCH";}}
  return null;
 }
 public IntegrityReport VerifyIntegrity(string? expectedHead=null)
 {
  string head=Genesis;long count=0;long? current=null;
  try{using var c=Open();Exec(c,"BEGIN");try{var reversed=new HashSet<long>();var keys=new HashSet<string>(StringComparer.Ordinal);foreach(var h in Headers(c)){current=h.Id;var why=Check(c,h,Lines(c,h.Id),head);if(why is not null)return new(false,count,head,current,why);if(h.ReversesId is long t&&!reversed.Add(t))return new(false,count,head,current,"DUPLICATE_REVERSAL");if(h.IdempotencyKey is string k&&!keys.Add(k))return new(false,count,head,current,"DUPLICATE_IDEMPOTENCY_KEY");head=h.Hash;count++;}
   using(var q=Command(c,"PRAGMA foreign_key_check")){using var r=q.ExecuteReader();if(r.Read())return new(false,count,head,null,"FOREIGN_KEY_VIOLATION");}
   if(expectedHead is not null&&head!=expectedHead)return new(false,count,head,null,"EXTERNAL_ANCHOR_MISMATCH");return new(true,count,head,null,null);
  }finally{Exec(c,"ROLLBACK");}}
  catch(LedgerException e) when(e.Code is "INTEGRITY_VIOLATION" or "AMOUNT_OVERFLOW"){return new(false,count,head,current,e.Code);}
  catch(Exception e) when(e is InvalidCastException or InvalidOperationException or OverflowException or FormatException or DecoderFallbackException){return new(false,count,head,current,"UNREADABLE_STORED_ROW");}
  catch(SqliteException e){throw new LedgerException("STORAGE_REJECTED",e.Message,e);}
 }
 // v2: null=-1:, otherwise UTF-8 byte count + ':' + UTF-8 bytes, all integers invariant.
 public static string CanonHash(params object?[] fields){using var bytes=new MemoryStream();var utf8=new UTF8Encoding(false,true);foreach(var f in fields){var s=f is null?null:f is IFormattable n?n.ToString(null,CultureInfo.InvariantCulture):f.ToString();if(s is null){bytes.Write(Encoding.ASCII.GetBytes("-1:"));continue;}var b=utf8.GetBytes(s);bytes.Write(Encoding.ASCII.GetBytes(b.Length.ToString(CultureInfo.InvariantCulture)+":"));bytes.Write(b);}return Convert.ToHexStringLower(SHA256.HashData(bytes.ToArray()));}
 public static string Fingerprint(StoredEntry h,IReadOnlyList<StoredLine> lines){var fields=new List<object?>{2,h.Date,h.Description,h.Currency,h.Reference,h.Type,h.CreatedBy,h.ReversesId,lines.Count};foreach(var l in lines)fields.AddRange([l.LineNo,l.AccountId,l.Currency,l.DebitOrig,l.CreditOrig,l.DebitBase,l.CreditBase,l.CustomerId,l.InvoiceId]);return CanonHash(fields.ToArray());}
 public static string EntryHash(string prev,string at,string? key,string fp)=>CanonHash(2,prev,at,key,fp);
 public GovernanceEvent Record(string kind,string entityId,JsonElement payload)
 {
  if(!new[]{"task","decision","evidence","hypothesis","document","release"}.Contains(kind))throw Error("INVALID_REQUEST","Unknown event kind");Text(entityId,120,"entity",true);
  if(payload.ValueKind!=JsonValueKind.Object)throw Error("INVALID_REQUEST","Payload must be object");
  if(payload.TryGetProperty("status",out var status)&&status.ValueKind==JsonValueKind.String&&new[]{"VERIFIED","PRODUCTION_READY","PASS"}.Contains(status.GetString()))throw Error("STATUS_GATE","Evidence submissions cannot grant verified/PASS/production status");
  var json=JsonSerializer.Serialize(payload);if(Encoding.UTF8.GetByteCount(json)>65536)throw Error("INVALID_REQUEST","Payload too large");
  return Write(c=>{var seq=Convert.ToInt64(Scalar(c,"SELECT COALESCE(MAX(seq),0)+1 FROM governance_events"),CultureInfo.InvariantCulture);var prev=Scalar(c,"SELECT event_hash FROM governance_events ORDER BY seq DESC LIMIT 1") as string??Genesis;var at=At();var hash=CanonHash(2,seq,at,kind,entityId,json,prev);Exec(c,"INSERT INTO governance_events VALUES($s,$a,$k,$i,$p,$prev,$h)",("$s",seq),("$a",at),("$k",kind),("$i",entityId),("$p",json),("$prev",prev),("$h",hash));return new GovernanceEvent(seq,at,kind,entityId,json,prev,hash);});
 }
 public IReadOnlyList<GovernanceEvent> ExportEvents(){using var c=Open();using var q=Command(c,"SELECT seq,at,kind,entity_id,payload,prev_hash,event_hash FROM governance_events ORDER BY seq");using var r=q.ExecuteReader();var events=new List<GovernanceEvent>();while(r.Read())events.Add(new(r.GetInt64(0),r.GetString(1),r.GetString(2),r.GetString(3),r.GetString(4),r.GetString(5),r.GetString(6)));return events;}
 public ReplayReport Replay(){using var c=Open();using var q=Command(c,"SELECT seq,at,kind,entity_id,payload,prev_hash,event_hash FROM governance_events ORDER BY seq");using var r=q.ExecuteReader();var head=Genesis;long n=0;var state=new SortedDictionary<string,JsonElement>(StringComparer.Ordinal);while(r.Read()){var seq=r.GetInt64(0);var at=r.GetString(1);var kind=r.GetString(2);var id=r.GetString(3);var payload=r.GetString(4);var prev=r.GetString(5);var hash=r.GetString(6);if(seq!=n+1||prev!=head||hash!=CanonHash(2,seq,at,kind,id,payload,prev))return new(false,n,head,"EVENT_CHAIN_INVALID",state);using var doc=JsonDocument.Parse(payload);state[kind+":"+id]=doc.RootElement.Clone();head=hash;n++;}return new(true,n,head,null,state);}
}
