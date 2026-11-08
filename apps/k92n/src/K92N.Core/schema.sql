-- NEW EMPTY DATABASE ONLY. SQLite >= 3.37. Existing databases require a reviewed migration.
PRAGMA foreign_keys=ON;
CREATE TABLE system_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL) STRICT, WITHOUT ROWID;
INSERT INTO system_meta VALUES('schema_version','1'),('hash_contract','2');
CREATE TABLE currencies(code TEXT PRIMARY KEY CHECK(length(code)=3 AND code NOT GLOB '*[^A-Z]*'),minor_units INTEGER NOT NULL CHECK(minor_units BETWEEN 0 AND 6)) STRICT, WITHOUT ROWID;
INSERT INTO currencies VALUES('USD',2),('TRY',2),('SYP',0),('EUR',2),('GBP',2),('SAR',2),('AED',2),('QAR',2),('EGP',2),('KWD',3),('BHD',3),('OMR',3),('JOD',3),('JPY',0);
CREATE TABLE ledger_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL) STRICT, WITHOUT ROWID;
INSERT INTO ledger_meta VALUES('base_currency','USD');
CREATE TABLE accounts(id INTEGER PRIMARY KEY CHECK(id>0),code TEXT NOT NULL UNIQUE CHECK(length(code) BETWEEN 1 AND 40),name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 120)) STRICT;
CREATE TABLE period_locks(id INTEGER PRIMARY KEY AUTOINCREMENT,locked_through TEXT NOT NULL CHECK(length(locked_through)=10 AND locked_through GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND locked_through BETWEEN '0001-01-01' AND '9999-12-31' AND date(locked_through,'+0 days') IS locked_through),locked_at TEXT NOT NULL) STRICT;
CREATE TABLE journal_entries(
 id INTEGER PRIMARY KEY AUTOINCREMENT CHECK(id>0),
 entry_date TEXT NOT NULL CHECK(length(entry_date)=10 AND entry_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND entry_date BETWEEN '0001-01-01' AND '9999-12-31' AND date(entry_date,'+0 days') IS entry_date),
 description TEXT NOT NULL CHECK(length(trim(description)) BETWEEN 1 AND 500 AND instr(description,char(0))=0),
 currency_code TEXT NOT NULL REFERENCES currencies(code),
 reference TEXT CHECK(reference IS NULL OR (length(reference)<=100 AND instr(reference,char(0))=0)),
 entry_type TEXT NOT NULL CHECK(length(entry_type) BETWEEN 2 AND 32 AND entry_type NOT GLOB '*[^A-Z0-9_]*'),
 created_by INTEGER CHECK(created_by IS NULL OR created_by>0),
 idempotency_key TEXT CHECK(idempotency_key IS NULL OR (length(trim(idempotency_key)) BETWEEN 1 AND 100 AND instr(idempotency_key,char(0))=0)),
 reverses_entry_id INTEGER UNIQUE REFERENCES journal_entries(id),
 line_count INTEGER NOT NULL CHECK(line_count BETWEEN 2 AND 1000),
 total_base INTEGER NOT NULL CHECK(total_base BETWEEN 1 AND 1000000000000000000),
 posted_at TEXT NOT NULL CHECK(length(posted_at)=24 AND posted_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9]Z' AND julianday(posted_at) IS NOT NULL),
 hash_version INTEGER NOT NULL CHECK(hash_version=2),
 fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64 AND fingerprint NOT GLOB '*[^0-9a-f]*'),
 prev_hash TEXT NOT NULL UNIQUE CHECK(length(prev_hash)=64 AND prev_hash NOT GLOB '*[^0-9a-f]*'),
 entry_hash TEXT NOT NULL UNIQUE CHECK(length(entry_hash)=64 AND entry_hash NOT GLOB '*[^0-9a-f]*'),
 CHECK((entry_type='REVERSAL')=(reverses_entry_id IS NOT NULL))
) STRICT;
CREATE UNIQUE INDEX ux_journal_idem ON journal_entries(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE TABLE journal_lines(
 entry_id INTEGER NOT NULL REFERENCES journal_entries(id),
 line_no INTEGER NOT NULL CHECK(line_no BETWEEN 1 AND 1000),
 account_id INTEGER NOT NULL REFERENCES accounts(id),
 currency_code TEXT NOT NULL REFERENCES currencies(code),
 debit_orig INTEGER NOT NULL CHECK(debit_orig BETWEEN 0 AND 1000000000000000),
 credit_orig INTEGER NOT NULL CHECK(credit_orig BETWEEN 0 AND 1000000000000000),
 debit_base INTEGER NOT NULL CHECK(debit_base BETWEEN 0 AND 1000000000000000),
 credit_base INTEGER NOT NULL CHECK(credit_base BETWEEN 0 AND 1000000000000000),
 customer_id INTEGER CHECK(customer_id IS NULL OR customer_id>0),
 invoice_id INTEGER CHECK(invoice_id IS NULL OR invoice_id>0),
 PRIMARY KEY(entry_id,line_no),
 CHECK((debit_orig>0 AND debit_base>0 AND credit_orig=0 AND credit_base=0) OR (credit_orig>0 AND credit_base>0 AND debit_orig=0 AND debit_base=0))
) STRICT, WITHOUT ROWID;
CREATE INDEX ix_lines_account ON journal_lines(account_id,entry_id);
CREATE INDEX ix_lines_customer ON journal_lines(customer_id,account_id,entry_id) WHERE customer_id IS NOT NULL;
CREATE TABLE journal_seals(entry_id INTEGER PRIMARY KEY REFERENCES journal_entries(id),sealed_at TEXT NOT NULL) STRICT;
CREATE VIEW posted_lines AS SELECT l.* FROM journal_lines l JOIN journal_seals s ON s.entry_id=l.entry_id;
CREATE TRIGGER header_guard BEFORE INSERT ON journal_entries BEGIN
 SELECT RAISE(ABORT,'PERIOD_LOCKED') WHERE NEW.entry_date<=COALESCE((SELECT MAX(locked_through) FROM period_locks),'0000-00-00');
 SELECT RAISE(ABORT,'PREVIOUS_ENTRY_UNSEALED') WHERE EXISTS(SELECT 1 FROM journal_entries e LEFT JOIN journal_seals s ON s.entry_id=e.id WHERE s.entry_id IS NULL);
 SELECT RAISE(ABORT,'NON_MONOTONIC_ID') WHERE NEW.id<>-1 AND NEW.id<=COALESCE((SELECT MAX(id) FROM journal_entries),0);
 SELECT RAISE(ABORT,'CHAIN_LINK_BROKEN') WHERE NEW.prev_hash<>COALESCE((SELECT entry_hash FROM journal_entries ORDER BY id DESC LIMIT 1),printf('%064d',0));
 SELECT RAISE(ABORT,'REVERSAL_TARGET_INVALID') WHERE NEW.reverses_entry_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM journal_entries e JOIN journal_seals s ON s.entry_id=e.id WHERE e.id=NEW.reverses_entry_id);
END;
CREATE TRIGGER lines_guard BEFORE INSERT ON journal_lines BEGIN
 SELECT RAISE(ABORT,'ENTRY_SEALED') WHERE EXISTS(SELECT 1 FROM journal_seals WHERE entry_id=NEW.entry_id);
 SELECT RAISE(ABORT,'LINE_NO_INVALID') WHERE NEW.line_no<>1+(SELECT COUNT(*) FROM journal_lines WHERE entry_id=NEW.entry_id) OR NEW.line_no>COALESCE((SELECT line_count FROM journal_entries WHERE id=NEW.entry_id),0);
 SELECT RAISE(ABORT,'BASE_AMOUNT_MISMATCH') WHERE NEW.currency_code=(SELECT value FROM ledger_meta WHERE key='base_currency') AND (NEW.debit_orig<>NEW.debit_base OR NEW.credit_orig<>NEW.credit_base);
END;
CREATE TRIGGER seal_guard BEFORE INSERT ON journal_seals BEGIN
 SELECT RAISE(ABORT,'ENTRY_ALREADY_SEALED') WHERE EXISTS(SELECT 1 FROM journal_seals WHERE entry_id=NEW.entry_id);
 SELECT RAISE(ABORT,'SEAL_COUNT_MISMATCH') WHERE (SELECT COUNT(*) FROM journal_lines WHERE entry_id=NEW.entry_id)<>COALESCE((SELECT line_count FROM journal_entries WHERE id=NEW.entry_id),-1);
 SELECT RAISE(ABORT,'SEAL_TOTAL_MISMATCH') WHERE (SELECT SUM(debit_base) FROM journal_lines WHERE entry_id=NEW.entry_id)<>(SELECT total_base FROM journal_entries WHERE id=NEW.entry_id) OR (SELECT SUM(credit_base) FROM journal_lines WHERE entry_id=NEW.entry_id)<>(SELECT total_base FROM journal_entries WHERE id=NEW.entry_id);
 SELECT RAISE(ABORT,'REVERSAL_HEADER_MISMATCH') WHERE EXISTS(SELECT 1 FROM journal_entries r JOIN journal_entries o ON o.id=r.reverses_entry_id WHERE r.id=NEW.entry_id AND (r.currency_code<>o.currency_code OR r.reference IS NOT o.reference OR r.line_count<>o.line_count));
 SELECT RAISE(ABORT,'REVERSAL_MIRROR_MISMATCH') WHERE EXISTS(
  SELECT 1 FROM journal_entries r JOIN journal_lines a ON a.entry_id=r.id LEFT JOIN journal_lines o ON o.entry_id=r.reverses_entry_id AND o.line_no=a.line_no
  WHERE r.id=NEW.entry_id AND r.reverses_entry_id IS NOT NULL AND (o.line_no IS NULL OR a.account_id<>o.account_id OR a.currency_code<>o.currency_code OR a.customer_id IS NOT o.customer_id OR a.invoice_id IS NOT o.invoice_id OR a.debit_orig<>o.credit_orig OR a.credit_orig<>o.debit_orig OR a.debit_base<>o.credit_base OR a.credit_base<>o.debit_base));
END;
CREATE TRIGGER period_advance BEFORE INSERT ON period_locks BEGIN
 SELECT RAISE(ABORT,'PERIOD_MUST_ADVANCE') WHERE NEW.locked_through<=COALESCE((SELECT MAX(locked_through) FROM period_locks),'0000-00-00');
END;
CREATE TABLE governance_events(
 seq INTEGER PRIMARY KEY CHECK(seq>0),at TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('task','decision','evidence','hypothesis','document','release')),
 entity_id TEXT NOT NULL,payload TEXT NOT NULL CHECK(json_valid(payload)),prev_hash TEXT NOT NULL UNIQUE CHECK(length(prev_hash)=64),event_hash TEXT NOT NULL UNIQUE CHECK(length(event_hash)=64)
) STRICT;
CREATE TRIGGER system_meta_no_update BEFORE UPDATE ON system_meta BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER system_meta_no_delete BEFORE DELETE ON system_meta BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER currencies_no_update BEFORE UPDATE ON currencies BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER currencies_no_delete BEFORE DELETE ON currencies BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER ledger_meta_no_update BEFORE UPDATE ON ledger_meta BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER ledger_meta_no_delete BEFORE DELETE ON ledger_meta BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER accounts_no_update BEFORE UPDATE ON accounts BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER accounts_no_delete BEFORE DELETE ON accounts BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER period_locks_no_update BEFORE UPDATE ON period_locks BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER period_locks_no_delete BEFORE DELETE ON period_locks BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER journal_entries_no_update BEFORE UPDATE ON journal_entries BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER journal_entries_no_delete BEFORE DELETE ON journal_entries BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER journal_lines_no_update BEFORE UPDATE ON journal_lines BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER journal_lines_no_delete BEFORE DELETE ON journal_lines BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER journal_seals_no_update BEFORE UPDATE ON journal_seals BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER journal_seals_no_delete BEFORE DELETE ON journal_seals BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER governance_events_no_update BEFORE UPDATE ON governance_events BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER governance_events_no_delete BEFORE DELETE ON governance_events BEGIN SELECT RAISE(ABORT,'APPEND_ONLY_VIOLATION');END;
CREATE TRIGGER governance_insert_guard BEFORE INSERT ON governance_events BEGIN
 SELECT RAISE(ABORT,'EVENT_SEQUENCE_INVALID') WHERE NEW.seq<>COALESCE((SELECT MAX(seq)+1 FROM governance_events),1);
 SELECT RAISE(ABORT,'EVENT_CHAIN_INVALID') WHERE NEW.prev_hash<>COALESCE((SELECT event_hash FROM governance_events ORDER BY seq DESC LIMIT 1),printf('%064d',0));
 SELECT RAISE(ABORT,'STATUS_GATE') WHERE upper(COALESCE(json_extract(NEW.payload,'$.status'),'')) IN ('PASS','VERIFIED','PRODUCTION_READY');
END;
