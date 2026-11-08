#!/usr/bin/env python3
"""SQLite structural backup/restore to a NEW file; domain/anchor checks remain mandatory."""
import argparse,contextlib,hashlib,json,os,re,sqlite3,tempfile
from pathlib import Path

def file_sha256(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def validate_database(db):
 if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('SQLite integrity_check failed')
 if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('SQLite foreign_key_check failed')

def copy_database(source,destination,expected_sha256=None):
 source=Path(source).resolve();destination=Path(destination).resolve()
 if source==destination or destination.exists():raise ValueError('Destination must be a NEW path; existing files are never replaced')
 if not source.is_file():raise ValueError('Source database not found')
 if expected_sha256 is not None:
  if not re.fullmatch('[0-9a-f]{64}',expected_sha256):raise ValueError('Expected SHA-256 must be 64 lowercase hex characters')
  if file_sha256(source)!=expected_sha256:raise ValueError('Backup SHA-256 mismatch')
 destination.parent.mkdir(parents=True,exist_ok=True)
 fd,temp=tempfile.mkstemp(prefix='.k92n-backup-',suffix='.db',dir=destination.parent);os.close(fd);temp=Path(temp)
 try:
  with contextlib.ExitStack() as stack:
   src=stack.enter_context(contextlib.closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)))
   dst=stack.enter_context(contextlib.closing(sqlite3.connect(temp)))
   # One read snapshot for source checks and copy, including committed WAL data.
   src.execute('BEGIN')
   validate_database(src)
   src.backup(dst)
   validate_database(dst)
   src.execute('ROLLBACK')
  if expected_sha256 is not None and file_sha256(source)!=expected_sha256:raise ValueError('Backup changed during restore')
  with temp.open('rb') as f:os.fsync(f.fileno())
  os.link(temp,destination) # atomic no-overwrite; destination can never replace a live DB
  directory_fd=os.open(destination.parent,os.O_RDONLY)
  try:os.fsync(directory_fd)
  finally:os.close(directory_fd)
  return {'destination':str(destination),'sha256':file_sha256(destination),'scope':'SQLite integrity/FK checked; ledger semantics and external anchor still require verification'}
 finally:temp.unlink(missing_ok=True)

def restore_database(source,destination,expected_sha256=None):
 source=Path(source).resolve();destination=Path(destination).resolve()
 if source==destination or destination.exists():raise ValueError('Destination must be a NEW path; existing files are never replaced')
 if not source.is_file():raise ValueError('Source database not found')
 def reject_sidecars():
  for suffix in ['-wal','-journal']:
   sidecar=Path(str(source)+suffix)
   if sidecar.exists() and sidecar.stat().st_size>0:raise ValueError('Restore requires a standalone backup, not a database with WAL/journal dependencies')
 reject_sidecars()
 # Freeze only the transported bytes before SQLite opens them; never consult mutable
 # sidecars beside the input or the original live database during restore.
 with tempfile.TemporaryDirectory(prefix='k92n-restore-input-') as td:
  frozen=Path(td)/'input.db'
  with source.open('rb') as inp,frozen.open('xb') as out:
   for block in iter(lambda:inp.read(1024*1024),b''):out.write(block)
   out.flush();os.fsync(out.fileno())
  reject_sidecars()
  return copy_database(frozen,destination,expected_sha256)

def main():
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['backup','restore-new']);p.add_argument('source');p.add_argument('destination');p.add_argument('--expected-sha256');a=p.parse_args()
 if a.operation=='backup' and a.expected_sha256:p.error('--expected-sha256 is for offline restore input, not a live WAL database')
 operation=restore_database if a.operation=='restore-new' else copy_database
 print(json.dumps(operation(a.source,a.destination,a.expected_sha256),indent=2))
if __name__=='__main__':main()
