"""Static checks for repository Git safety guardrails."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class GitSafetyPolicyTests(unittest.TestCase):
    def test_inspection_script_is_read_only(self):
        script = (ROOT / "scripts/safe-git.sh").read_text()
        self.assertIn("git status --short", script)
        self.assertIn("git fetch --dry-run origin", script)
        for forbidden in ("git reset --hard", "git clean -fd", "git push --force", "git checkout -B"):
            self.assertNotIn(forbidden, script)

    def test_policy_declares_protected_branches(self):
        policy = (ROOT / "docs/GIT-SAFETY-POLICY.md").read_text()
        self.assertIn("main", policy)
        self.assertIn("recovery/*", policy)
        self.assertIn("source-build", policy)
        self.assertIn("do **not** authorize production", policy)

if __name__ == "__main__":
    unittest.main()
