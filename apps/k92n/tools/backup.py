#!/usr/bin/env python3
"""Consistent SQLite backup/restore-to-NEW-file. Does not certify ledger semantics."""
import argparse,hashlib,json,os,sqlite3,tempfile
from pathlib import Path

def copy_database(source,destination):
 source=Path(source).resolve();destination=Path(destination).resolve()
 if source==destination or destination.exists():raise ValueError('Destination must be a NEW path; existing files are never replaced')
 if not source.is_file():raise ValueError('Source database not found')
 destination.parent.mkdir(parents=True,exist_ok=True)
 fd,temp=tempfile.mkstemp(prefix='.k92n-backup-',suffix='.db',dir=destination.parent);os.close(fd);temp=Path(temp)
 try:
  src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);dst=sqlite3.connect(temp)
  try:
   if src.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('Source quick_check failed')
   src.backup(dst)
   if dst.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('Backup quick_check failed')
  finally:dst.close();src.close()
  # Atomic no-overwrite publication; same filesystem as destination.
  os.link(temp,destination)
  return {'destination':str(destination),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'scope':'SQLite structural backup; domain verification still required'}
 finally:temp.unlink(missing_ok=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['backup','restore-new']);p.add_argument('source');p.add_argument('destination');a=p.parse_args()
 print(json.dumps(copy_database(a.source,a.destination),indent=2))
if __name__=='__main__':main()
