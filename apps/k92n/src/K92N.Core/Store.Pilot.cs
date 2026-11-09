using System.Globalization;
using Microsoft.Data.Sqlite;
namespace K92N.Core;

public sealed record AccountView(string Id,string Code,string Name);
public sealed record CurrencyView(string Code,int MinorUnits,bool IsBase);
public sealed record StatementLine(string EntryId,string LineNo,string Date,string Description,string EntryType,string Currency,string DebitMinor,string CreditMinor,string DebitBaseMinor,string CreditBaseMinor,string? ReversesEntryId,bool IsReversed);
public sealed record StatementCursor(string EntryId,string LineNo);
public sealed record CustomerStatement(string CustomerId,string AccountId,Dictionary<string,string> Balances,IReadOnlyList<StatementLine> Lines,StatementCursor? Next);

public sealed partial class Store
{
 static string Number(long value)=>value.ToString(CultureInfo.InvariantCulture);
 T Read<T>(Func<SqliteConnection,T> work)
 {
  try{using var c=Open();Exec(c,"BEGIN");try{return work(c);}finally{Exec(c,"ROLLBACK");}}
  catch(SqliteException e){throw new LedgerException(e.SqliteErrorCode is 5 or 6?"BUSY":"STORAGE_REJECTED","Read rejected",e);}
 }
 public IReadOnlyList<AccountView> Accounts()=>Read<IReadOnlyList<AccountView>>(c=>{
  using var q=Command(c,"SELECT id,code,name FROM accounts ORDER BY id");using var r=q.ExecuteReader();var rows=new List<AccountView>();
  while(r.Read())rows.Add(new(Number(r.GetInt64(0)),r.GetString(1),r.GetString(2)));return rows;
 });
 public IReadOnlyList<CurrencyView> Currencies()=>currencies.OrderBy(p=>p.Key,StringComparer.Ordinal).Select(p=>new CurrencyView(p.Key,p.Value,p.Key=="USD")).ToArray();
 public CustomerStatement Statement(long customerId,long accountId,long? beforeEntryId=null,long? beforeLineNo=null,int limit=30)
 {
  if(customerId<=0||accountId<=0||limit<1||limit>100||beforeEntryId is <=0||beforeLineNo is <=0||(beforeEntryId is null)!=(beforeLineNo is null))throw Error("INVALID_REQUEST","Invalid statement page");
  return Read(c=>{
   var balances=new Dictionary<string,string>(StringComparer.Ordinal);
   using(var q=Command(c,"SELECT currency_code,SUM(debit_orig-credit_orig) FROM posted_lines WHERE customer_id=$c AND account_id=$a GROUP BY currency_code",("$c",customerId),("$a",accountId))){using var r=q.ExecuteReader();while(r.Read())balances.Add(r.GetString(0),Number(r.GetInt64(1)));}
   using var cmd=Command(c,"""
    SELECT e.id,l.line_no,e.entry_date,e.description,e.entry_type,l.currency_code,
           l.debit_orig,l.credit_orig,l.debit_base,l.credit_base,e.reverses_entry_id,
           EXISTS(SELECT 1 FROM journal_entries rv JOIN journal_seals rs ON rs.entry_id=rv.id WHERE rv.reverses_entry_id=e.id)
    FROM posted_lines l JOIN journal_entries e ON e.id=l.entry_id
    WHERE l.customer_id=$c AND l.account_id=$a
      AND ($before IS NULL OR e.id<$before OR (e.id=$before AND l.line_no<$line))
    ORDER BY e.id DESC,l.line_no DESC LIMIT $take
    """,("$c",customerId),("$a",accountId),("$before",beforeEntryId),("$line",beforeLineNo),("$take",limit+1));
   using var reader=cmd.ExecuteReader();var rows=new List<StatementLine>();
   while(reader.Read())rows.Add(new(Number(reader.GetInt64(0)),Number(reader.GetInt64(1)),reader.GetString(2),reader.GetString(3),reader.GetString(4),reader.GetString(5),Number(reader.GetInt64(6)),Number(reader.GetInt64(7)),Number(reader.GetInt64(8)),Number(reader.GetInt64(9)),reader.IsDBNull(10)?null:Number(reader.GetInt64(10)),reader.GetInt64(11)!=0));
   StatementCursor? next=null;if(rows.Count>limit){rows.RemoveAt(rows.Count-1);var last=rows[^1];next=new(last.EntryId,last.LineNo);}
   return new CustomerStatement(Number(customerId),Number(accountId),balances,rows,next);
  });
 }
}
