#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "UER candidate: local isolated test host only. This script does not approve release."
command -v dotnet >/dev/null || { echo "BLOCKED: .NET SDK missing" >&2; exit 2; }
dotnet --list-sdks
dotnet restore source/blackwolf-uer-v0.1.1-reliability/src/Uer.Api/Uer.Api.csproj
dotnet build source/blackwolf-uer-v0.1.1-reliability/src/Uer.Api/Uer.Api.csproj -c Release --no-restore
dotnet restore tests/Uer.Api.StoreContracts/Uer.Api.StoreContracts.csproj
dotnet run --project tests/Uer.Api.StoreContracts -c Release --no-restore
echo "Only SQLite Store contracts tested. Docker 10 acceptance tests and 3 P1 gates STILL NOT VERIFIED."
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  echo "Docker detected: actual crash/recovery acceptance suite must be run separately on a dedicated disposable host."
else
  echo "Docker blocked/unavailable."
fi
