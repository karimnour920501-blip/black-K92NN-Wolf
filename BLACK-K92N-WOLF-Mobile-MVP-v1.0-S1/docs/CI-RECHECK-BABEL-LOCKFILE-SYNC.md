# S1 Metro Babel CI recheck

Evidence Gate #32 passed source gate, npm ci, Node tests, and TypeScript; Expo export failed because babel-preset-expo was absent. Added the preset to devDependencies and Lockfile Bootstrap #4 completed successfully. Evidence Gate #33 started before lockfile was refreshed; its npm ci failed EUSAGE with missing babel-preset-expo@54.0.12. This commit triggers a new Evidence Gate using the refreshed lockfile. Issue #10 remains OPEN until all jobs succeed; main unchanged.
