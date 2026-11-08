"""Real SQLite tests of the embedded SQL. These do NOT execute C# code."""
import hashlib,json,sqlite3,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCHEMA=(ROOT/'src/K92N.Core/schema.sql').read_text()
ZERO='0'*64
AT='2026-11-08T00:00:00.000Z'
def canon(*fields):
    data=b''
    for f in fields:
        if f is None:data+=b'-1:'
        else:
            b=str(f).encode('utf-8');data+=str(len(b)).encode()+b':'+b
    return hashlib.sha256(data).hexdigest()
def fingerprint(h,lines):
    fields=[2,h['date'],h['description'],h['currency'],h['reference'],h['type'],None,h['reverse'],len(lines)]
    for line in lines:fields.extend(line)
    return canon(*fields)
class SchemaTests(unittest.TestCase):
 def setUp(self):
    self.db=sqlite3.connect(':memory:',isolation_level=None)
    self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA recursive_triggers=ON')
    self.db.executescript(SCHEMA)
    self.db.execute("INSERT INTO accounts VALUES(1,'1000','Cash'),(2,'1200','Receivables')")
 def tearDown(self):self.db.close()
 def header(self,lines=None,**changes):
    lines=lines or [(1,1,'USD',100,0,100,0,None,None),(2,2,'USD',0,100,0,100,None,None)]
    h=dict(date='2026-11-08',description='Test',currency='USD',reference=None,type='INVOICE',reverse=None)
    h.update({k:v for k,v in changes.items() if k in h})
    prev=self.db.execute('SELECT entry_hash FROM journal_entries ORDER BY id DESC LIMIT 1').fetchone()
    prev=prev[0] if prev else ZERO
    fp=fingerprint(h,lines);eh=canon(2,prev,AT,changes.get('key'),fp)
    cols=['entry_date','description','currency_code','reference','entry_type','created_by','idempotency_key','reverses_entry_id','line_count','total_base','posted_at','hash_version','fingerprint','prev_hash','entry_hash']
    values=[h['date'],h['description'],h['currency'],h['reference'],h['type'],None,changes.get('key'),h['reverse'],changes.get('count',len(lines)),changes.get('total',100),changes.get('at',AT),2,fp,prev,eh]
    for i,key in enumerate(cols):
      if key in changes:values[i]=changes[key]
    return self.db.execute('INSERT INTO journal_entries('+','.join(cols)+') VALUES('+','.join('?'*len(cols))+') RETURNING id',values).fetchone()[0]
 def lines(self,id,lines=None):
    lines=lines or [(1,1,'USD',100,0,100,0,None,None),(2,2,'USD',0,100,0,100,None,None)]
    for line in lines:self.db.execute('INSERT INTO journal_lines VALUES('+','.join('?'*10)+')',(id,*line))
 def seal(self,id):self.db.execute('INSERT INTO journal_seals VALUES(?,?)',(id,AT))
 def post(self,lines=None,**kw):
    self.db.execute('BEGIN IMMEDIATE')
    try:
      id=self.header(lines,**kw);self.lines(id,lines);self.seal(id);self.db.execute('COMMIT');return id
    except:
      self.db.execute('ROLLBACK');raise
 def rejects(self,fn,part):
    with self.assertRaises(sqlite3.IntegrityError) as e:fn()
    self.assertIn(part,str(e.exception))
 def test_valid_post_and_seal(self):
    self.post();self.assertEqual(self.db.execute('SELECT count(*) FROM posted_lines').fetchone()[0],2)
 def test_unsealed_lines_not_posted(self):
    id=self.header();self.lines(id);self.assertEqual(self.db.execute('SELECT count(*) FROM posted_lines').fetchone()[0],0)
 def test_incomplete_seal_rejected(self):
    id=self.header();self.rejects(lambda:self.seal(id),'SEAL_COUNT_MISMATCH')
 def test_unbalanced_seal_rejected_and_transaction_rollback(self):
    lines=[(1,1,'USD',100,0,100,0,None,None),(2,2,'USD',0,99,0,99,None,None)]
    self.rejects(lambda:self.post(lines),'SEAL_TOTAL_MISMATCH')
    self.assertEqual(self.db.execute('SELECT count(*) FROM journal_entries').fetchone()[0],0)
 def test_insert_after_seal_rejected(self):
    id=self.post();self.rejects(lambda:self.lines(id,[(3,1,'USD',1,0,1,0,None,None)]),'ENTRY_SEALED')
 def test_update_and_delete_blocked(self):
    self.post()
    for table in ['journal_entries','journal_lines','journal_seals','accounts','currencies','ledger_meta']:
      for op in ['UPDATE','DELETE']:
       with self.subTest(table=table,op=op):
        col=self.db.execute(f'PRAGMA table_info({table})').fetchone()[1]
        sql=f'UPDATE {table} SET {col}={col}' if op=='UPDATE' else f'DELETE FROM {table}'
        self.rejects(lambda:self.db.execute(sql),'APPEND_ONLY_VIOLATION')
 def test_replace_seal_blocked(self):
    id=self.post();self.rejects(lambda:self.db.execute('INSERT OR REPLACE INTO journal_seals VALUES(?,?)',(id,AT)),'ENTRY_ALREADY_SEALED')
 def test_previous_unsealed_blocks_next(self):
    self.header();self.rejects(lambda:self.header(description='Next'),'PREVIOUS_ENTRY_UNSEALED')
 def test_chain_link_rejected(self):self.rejects(lambda:self.header(prev_hash='1'*64),'CHAIN_LINK_BROKEN')
 def test_invalid_dates(self):
    for d in ['2026-13-45','2026-12-00','2026-02-30','2026-11-31','0000-01-01','2026-1-01','not-a-date']:
      with self.subTest(date=d):self.rejects(lambda:self.header(date=d),'CHECK constraint failed')
 def test_valid_leap_date(self):self.post(date='2024-02-29')
 def test_invalid_period_date(self):self.rejects(lambda:self.db.execute("INSERT INTO period_locks(locked_through,locked_at) VALUES('2026-13-45',?)",(AT,)),'CHECK constraint failed')
 def test_period_lock_and_monotonicity(self):
    self.db.execute("INSERT INTO period_locks(locked_through,locked_at) VALUES('2026-11-07',?)",(AT,))
    self.rejects(lambda:self.header(date='2026-11-07'),'PERIOD_LOCKED')
    self.rejects(lambda:self.db.execute("INSERT INTO period_locks(locked_through,locked_at) VALUES('2026-11-06',?)",(AT,)),'PERIOD_MUST_ADVANCE')
 def test_type_and_field_limits(self):
    for changes in [dict(type='lower'),dict(type='AB CD'),dict(description='x'*501),dict(reference='r'*101),dict(key='k'*101),dict(key='   '),dict(description='a\x00b')]:
      with self.subTest(changes=changes):self.rejects(lambda:self.header(**changes),'CHECK constraint failed')
 def test_hash_format(self):
    for k in ['fingerprint','prev_hash','entry_hash']:
      # Drop only the chain trigger so CHECK is the cause under test.
      if k=='prev_hash':self.db.execute('DROP TRIGGER header_guard')
      with self.subTest(field=k):self.rejects(lambda:self.header(**{k:'A'*64}),'CHECK constraint failed')
 def test_header_numeric_bounds(self):
    for kw in [dict(count=10**12),dict(count=1),dict(total=10**18+1),dict(total=0)]:
      with self.subTest(kw=kw):self.rejects(lambda:self.header(**kw),'CHECK constraint failed')
 def test_line_numbers_even_without_triggers(self):
    self.db.execute('DROP TRIGGER lines_guard');id=self.header()
    for n in [0,3_000_000_000]:
      self.rejects(lambda:self.lines(id,[(n,1,'USD',1,0,1,0,None,None)]),'CHECK constraint failed')
 def test_negative_and_excess_amounts(self):
    id=self.header()
    for amt in [-1,10**15+1]:self.rejects(lambda:self.lines(id,[(1,1,'USD',amt,0,amt,0,None,None)]),'CHECK constraint failed')
 def test_line_sides_and_base_currency(self):
    id=self.header()
    for line,error in [((1,1,'USD',1,1,1,1,None,None),'CHECK constraint failed'),((1,1,'USD',0,0,0,0,None,None),'CHECK constraint failed'),((1,1,'USD',2,0,1,0,None,None),'BASE_AMOUNT_MISMATCH')]:self.rejects(lambda:self.lines(id,[line]),error)
 def test_customer_and_invoice_ids(self):
    id=self.header()
    for customer,invoice in [(-1,None),(None,0)]:self.rejects(lambda:self.lines(id,[(1,1,'USD',1,0,1,0,customer,invoice)]),'CHECK constraint failed')
 def test_foreign_currency_base_and_original(self):
    lines=[(1,1,'KWD',1000,0,325,0,None,None),(2,2,'USD',0,325,0,325,None,None)]
    self.post(lines,total=325)
    self.assertEqual(self.db.execute("SELECT debit_orig,debit_base FROM posted_lines WHERE currency_code='KWD'").fetchone(),(1000,325))
 def test_foreign_keys(self):
    id=self.header();self.rejects(lambda:self.lines(id,[(1,999,'USD',1,0,1,0,None,None)]),'FOREIGN KEY constraint failed')
 def test_reversal_tags(self):
    id=self.post()
    self.rejects(lambda:self.header(type='REVERSAL'),'CHECK constraint failed')
    self.rejects(lambda:self.header(reverse=id),'CHECK constraint failed')
 def test_valid_mirror(self):
    id=self.post();lines=[(1,1,'USD',0,100,0,100,None,None),(2,2,'USD',100,0,100,0,None,None)]
    self.post(lines,type='REVERSAL',reverse=id)
 def test_fabricated_reversal_valid_hashes_rejected_on_seal(self):
    id=self.post()
    # header helper computes real v2 hashes for these wrong-but-balanced lines.
    wrong=[(1,1,'USD',0,50,0,50,None,None),(2,2,'USD',50,0,50,0,None,None)]
    self.rejects(lambda:self.post(wrong,type='REVERSAL',reverse=id,total=50),'REVERSAL_MIRROR_MISMATCH')
    self.assertEqual(self.db.execute('SELECT count(*) FROM journal_entries').fetchone()[0],1)
 def test_double_reversal(self):
    id=self.post();lines=[(1,1,'USD',0,100,0,100,None,None),(2,2,'USD',100,0,100,0,None,None)]
    self.post(lines,type='REVERSAL',reverse=id)
    self.rejects(lambda:self.post(lines,type='REVERSAL',reverse=id,description='Again'),'UNIQUE constraint failed')
 def test_reversal_header_reference(self):
    id=self.post(reference='invoice-1');lines=[(1,1,'USD',0,100,0,100,None,None),(2,2,'USD',100,0,100,0,None,None)]
    self.rejects(lambda:self.post(lines,type='REVERSAL',reverse=id,reference='other'),'REVERSAL_HEADER_MISMATCH')
 def test_unique_idempotency(self):
    self.post(key='request-1');self.rejects(lambda:self.post(description='other',key='request-1'),'UNIQUE constraint failed')
 def test_governance_sequence_and_status_gate(self):
    self.rejects(lambda:self.db.execute('INSERT INTO governance_events VALUES(2,?,?,?,?,?,?)',(AT,'task','t','{}',ZERO,'a'*64)),'EVENT_SEQUENCE_INVALID')
    self.rejects(lambda:self.db.execute('INSERT INTO governance_events VALUES(1,?,?,?,?,?,?)',(AT,'evidence','e','{"status":"VERIFIED"}',ZERO,'a'*64)),'STATUS_GATE')
 def test_governance_record_is_append_only(self):
    p='{"status":"RECORDED","text":"submitted evidence"}'
    h=canon(2,1,AT,'evidence','e',p,ZERO)
    self.db.execute('INSERT INTO governance_events VALUES(1,?,?,?,?,?,?)',(AT,'evidence','e',p,ZERO,h))
    self.rejects(lambda:self.db.execute('DELETE FROM governance_events'),'APPEND_ONLY_VIOLATION')
if __name__=='__main__':unittest.main()
