#!/usr/bin/env bash
set -euo pipefail

# Read-only Git safety checks. Never resets, cleans, pushes or switches branches.
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
branch="$(git symbolic-ref --quiet --short HEAD || true)"
printf 'Repository: %s\nBranch: %s\n' "$repo_root" "${branch:-DETACHED}"
git status --short
git fetch --dry-run origin >/dev/null
case "$branch" in
  main|recovery/*) echo "Protected branch: destructive operations are prohibited." ;;
  *) echo "Feature branch: review changes before editing history." ;;
esac
echo "Read-only safety inspection complete."
