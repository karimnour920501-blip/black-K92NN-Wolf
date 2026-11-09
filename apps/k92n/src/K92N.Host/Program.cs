using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using K92N.Core;

var token=Environment.GetEnvironmentVariable("K92N_OPERATOR_TOKEN");
if(string.IsNullOrWhiteSpace(token)||token.Length<32)throw new InvalidOperationException("Set K92N_OPERATOR_TOKEN to a random value of at least 32 characters; never commit it.");
var expected=SHA256.HashData(Encoding.UTF8.GetBytes(token));
var builder=WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls(Environment.GetEnvironmentVariable("ASPNETCORE_URLS")??"http://127.0.0.1:5080");
builder.WebHost.ConfigureKestrel(o=>o.Limits.MaxRequestBodySize=1_048_576);
var data=Environment.GetEnvironmentVariable("K92N_DATA_DIR")??Path.Combine(AppContext.BaseDirectory,".runtime");
builder.Services.AddSingleton(new Store(new LedgerOptions(Path.Combine(data,"k92n-local.db"))));
var app=builder.Build();
app.Use(async(context,next)=>{
 context.Response.Headers["X-Content-Type-Options"]="nosniff";
 context.Response.Headers["Referrer-Policy"]="no-referrer";
 context.Response.Headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'";
 if(context.Request.Path.StartsWithSegments("/api")){
  context.Response.Headers["Cache-Control"]="no-store";
  var auth=context.Request.Headers.Authorization.ToString();
  if(!auth.StartsWith("Bearer ",StringComparison.Ordinal)||!CryptographicOperations.FixedTimeEquals(expected,SHA256.HashData(Encoding.UTF8.GetBytes(auth[7..])))){context.Response.StatusCode=401;await context.Response.WriteAsJsonAsync(new{error="UNAUTHORIZED"});return;}
 }
 var sw=Stopwatch.StartNew();
 try{await next(context);}
 catch(LedgerException e){context.Response.StatusCode=e.Code=="BUSY"?503:e.Code=="IDEMPOTENCY_CONFLICT"?409:422;await context.Response.WriteAsJsonAsync(new{error=e.Code,message="Operation rejected. Consult the local operator log."});app.Logger.LogWarning("Rejected {Code}; trace {TraceId}",e.Code,context.TraceIdentifier);}
 catch(BadHttpRequestException){context.Response.StatusCode=400;await context.Response.WriteAsJsonAsync(new{error="INVALID_HTTP_REQUEST"});}
 catch(JsonException){context.Response.StatusCode=400;await context.Response.WriteAsJsonAsync(new{error="INVALID_JSON"});}
 finally{app.Logger.LogInformation("HTTP {Method} {Path} {Status} {ElapsedMs}ms trace={Trace}",context.Request.Method,context.Request.Path,context.Response.StatusCode,sw.ElapsedMilliseconds,context.TraceIdentifier);}
});
app.UseDefaultFiles();app.UseStaticFiles();
app.MapGet("/healthz",()=>Results.Ok(new{status="running",productionReady=false,version="1.0.2-pilot-candidate"}));
app.MapGet("/api/status",()=>new{version="1.0.2-pilot-candidate",productionReady=false,source="visible conversation",accountingStore="SQLite local",financeP0="DESIGN_ONLY / PostgreSQL separate",oidc="NOT_IMPLEMENTED",creditLimit="DEFERRED",verification="See GitHub CI evidence for the tested commit"});
app.MapPost("/api/accounts",(AccountInput a,Store s)=>{s.CreateAccount(a.Id,a.Code,a.Name);return Results.Created($"/api/accounts/{a.Id}",new{id=a.Id});});
app.MapPost("/api/journal_entries",(PostEntryRequest r,Store s)=>Results.Ok(new{id=s.PostEntry(r)}));
app.MapPost("/api/journal_entries/{id:long}/reversal",(long id,ReverseInput r,Store s)=>Results.Ok(new{id=s.ReverseEntry(id,r.Date,r.Reason,r.IdempotencyKey)}));
app.MapPost("/api/period_locks",(LockInput r,Store s)=>Results.Ok(new{id=s.LockPeriod(r.Through)}));
app.MapGet("/api/integrity",(string? expectedHead,Store s)=>s.VerifyIntegrity(expectedHead));
app.MapGet("/api/customers/{id:long}/balances",(long id,long accountId,Store s)=>s.CustomerBalances(id,accountId));
app.MapPost("/api/events",(EventInput e,Store s)=>s.Record(e.Kind,e.EntityId,e.Payload));
app.MapGet("/api/events",(Store s)=>s.ExportEvents());
app.MapGet("/api/replay",(Store s)=>s.Replay());
app.MapPilot();
app.Run();
public sealed record AccountInput(long Id,string Code,string Name);
public sealed record ReverseInput(DateOnly Date,string Reason,string? IdempotencyKey=null);
public sealed record LockInput(DateOnly Through);
public sealed record EventInput(string Kind,string EntityId,JsonElement Payload);
