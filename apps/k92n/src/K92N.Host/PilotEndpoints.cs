using System.Globalization;
using System.Text.RegularExpressions;
using K92N.Core;

public sealed record PilotPostingInput(string CustomerId,string ControlAccountId,string CounterAccountId,DateOnly EntryDate,string Kind,string CurrencyCode,string Amount,string? BaseAmount,string Description,string IdempotencyKey);
public sealed record PilotAccountInput(string Id,string Code,string Name);
public sealed record PilotReversalInput(string EntryId,DateOnly Date,string Reason,string IdempotencyKey);
public static partial class PilotEndpoints
{
 [GeneratedRegex(@"^[0-9]+(?:\.[0-9]+)?$",RegexOptions.CultureInvariant)]
 private static partial Regex AmountPattern();
 private static decimal Amount(string? value)
 {
  if(value is null||value.Length>32||!AmountPattern().IsMatch(value)||!decimal.TryParse(value,NumberStyles.AllowDecimalPoint,CultureInfo.InvariantCulture,out var number)||number<=0)throw new LedgerException("INVALID_REQUEST","Positive decimal amount required");
  return number;
 }
 private static long Id(string? value)
 {
  if(value is null||value.Length>19||!long.TryParse(value,NumberStyles.None,CultureInfo.InvariantCulture,out var id)||id<=0)throw new LedgerException("INVALID_REQUEST","Positive identifier required");
  return id;
 }
 public static void MapPilot(this WebApplication app)
 {
  app.MapGet("/api/accounts",(Store s)=>s.Accounts());
  app.MapGet("/api/currencies",(Store s)=>s.Currencies());
  app.MapGet("/api/customers/{id:long}/statement",(long id,long accountId,long? beforeEntryId,long? beforeLineNo,int? limit,Store s)=>s.Statement(id,accountId,beforeEntryId,beforeLineNo,limit??30));
  app.MapPost("/api/pilot/accounts",(PilotAccountInput input,Store s)=>{var id=Id(input.Id);s.CreateAccount(id,input.Code,input.Name);return Results.Created("/api/accounts/"+id.ToString(CultureInfo.InvariantCulture),new{id=id.ToString(CultureInfo.InvariantCulture)});});
  app.MapPost("/api/pilot/reversals",(PilotReversalInput input,Store s)=>{if(string.IsNullOrWhiteSpace(input.IdempotencyKey))throw new LedgerException("INVALID_REQUEST","Idempotency key required");var id=s.ReverseEntry(Id(input.EntryId),input.Date,input.Reason,key:input.IdempotencyKey);return Results.Ok(new{id=id.ToString(CultureInfo.InvariantCulture)});});
  app.MapPost("/api/pilot/postings",(PilotPostingInput input,Store s)=>{
   var customer=Id(input.CustomerId);var control=Id(input.ControlAccountId);var counter=Id(input.CounterAccountId);
   if(control==counter||input.Kind is not ("DEBT" or "PAYMENT")||string.IsNullOrWhiteSpace(input.IdempotencyKey))throw new LedgerException("INVALID_REQUEST","Invalid posting");
   var orig=Amount(input.Amount);var basis=input.CurrencyCode=="USD"?orig:Amount(input.BaseAmount);
   // Decimal strings are parsed server-side. JavaScript never rounds a financial amount.
   var debt=input.Kind=="DEBT";
   var lines=new[]{new JournalLineDto(control,input.CurrencyCode,debt?orig:0,debt?0:orig,debt?basis:0,debt?0:basis,customer),new JournalLineDto(counter,input.CurrencyCode,debt?0:orig,debt?orig:0,debt?0:basis,debt?basis:0)};
   var id=s.PostEntry(new PostEntryRequest(input.EntryDate,input.Description,input.CurrencyCode,null,input.Kind,null,lines,input.IdempotencyKey));
   return Results.Ok(new{id=id.ToString(CultureInfo.InvariantCulture)});
  });
 }
}
