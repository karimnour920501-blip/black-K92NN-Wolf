#!/usr/bin/env bash
set -euo pipefail
gh api -X PUT "repos/karimnour920501-blip/black-K92NN-Wolf/branches/main/protection" --input .github/branch-protection.json
