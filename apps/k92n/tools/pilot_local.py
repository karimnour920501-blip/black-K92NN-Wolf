#!/usr/bin/env python3
"""Start the built pilot on loopback; generate a private operator secret without logging it."""
import argparse,os,secrets,stat
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def operator_secret(path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 try:
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 except FileExistsError:pass
 else:
  with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(48)+'\n')
 if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode)&0o077:raise ValueError('Operator secret must be a private regular file (mode 0600)')
 token=path.read_text().strip()
 if len(token)<32:raise ValueError('Operator secret is too short')
 return token

def main():
 p=argparse.ArgumentParser();p.add_argument('--dotnet',default='dotnet');p.add_argument('--port',type=int,default=5080);a=p.parse_args()
 if not 1<=a.port<=65535:p.error('Port must be 1..65535')
 assembly=ROOT/'src/K92N.Host/bin/Release/net10.0/K92N.Host.dll'
 if not assembly.is_file():p.error('Run dotnet build src/K92N.Host/K92N.Host.csproj -c Release first')
 runtime=ROOT/'.runtime';secret=runtime/'operator-token';token=operator_secret(secret)
 env=os.environ.copy();env.update(K92N_OPERATOR_TOKEN=token,K92N_DATA_DIR=str(runtime/'data'),ASPNETCORE_URLS=f'http://127.0.0.1:{a.port}',ASPNETCORE_ENVIRONMENT='Production')
 print(f'Pilot: http://127.0.0.1:{a.port}\nOperator secret file (not printed): {secret}\nSynthetic data only. No paid hosting created.',flush=True)
 os.chdir(ROOT/'src/K92N.Host');os.execvpe(a.dotnet,[a.dotnet,str(assembly)],env)
if __name__=='__main__':main()
