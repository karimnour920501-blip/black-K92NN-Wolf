#!/bin/bash
set -euo pipefail
fail() { printf '%s\n' "K92N_STARTUP_REJECTED: $1" >&2; exit 78; }
token=${K92N_OPERATOR_TOKEN:-}
[[ ${#token} -ge 32 ]] || fail 'operator token must contain at least 32 characters'
port=${PORT:-10000}
[[ "$port" =~ ^[0-9]{1,5}$ ]] || fail 'invalid PORT'
(( 10#$port >= 1 && 10#$port <= 65535 )) || fail 'invalid PORT'
mount_dir=$(realpath -e "${K92N_DATA_MOUNT:-/data}") || fail 'data mount does not exist'
[[ "$mount_dir" != / ]] || fail 'root filesystem is not a data mount'
mountpoint -q -- "$mount_dir" || fail 'persistent disk is not mounted'
data_dir=$(realpath -m "${K92N_DATA_DIR:-/data/k92n}")
[[ "$data_dir" == "$mount_dir/"* ]] || fail 'data directory must be inside persistent mount'
mkdir -p -- "$data_dir" || fail 'data directory is not writable by runtime user'
probe=$(mktemp "$data_dir/.k92n-write-check.XXXXXXXX") || fail 'persistent data directory is not writable'
rm -- "$probe"
export K92N_DATA_DIR="$data_dir"
port=$((10#$port))
export ASPNETCORE_URLS="http://0.0.0.0:$port"
export ASPNETCORE_ENVIRONMENT=Production
umask 077
exec dotnet K92N.Host.dll
