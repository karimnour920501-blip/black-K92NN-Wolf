# Git Safety Policy — BLACK-K92N-WOLF

Scope: `main`, `recovery/*`, and all contributors.

## Rules
1. Preserve published history. Prefer `git revert <sha>` for shared commits.
2. Never automate `git reset --hard`, `git clean -fd`, `git push --force`, or `git checkout -B` on protected/recovery branches.
3. Never create a missing recovery branch from the current HEAD. Verify its upstream and provenance first.
4. Check `git status --porcelain` before switching branches. `git stash push -u` may preserve tracked and untracked changes but does not include ignored files.
5. Use `git cherry-pick -x <sha>` only after verifying source SHA, target branch, and clean worktree; resolve conflicts explicitly.
6. Avoid destructive local commands without explicit review and backup.
7. Recovery tests and successful CI do **not** authorize production deployment.

## Safe inspection
```bash
bash scripts/safe-git.sh
git branch -avv
git log --oneline --decorate -10
```

## GitHub protection (administrator action required)
For `main`, configure required pull requests, required `source-build` check, conversation resolution, restrict deletions, and block force pushes in GitHub Rulesets. Remove unnecessary bypass permissions after confirming administrator recovery access. This document cannot enforce server-side rules.
