import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class SourceContractTests(unittest.TestCase):
    def test_command_catalog(self):
        catalog = json.loads((ROOT / "src/Wolf.Commands.Api/commands.json").read_text())
        self.assertEqual(len(catalog["commands"]), 100)
        self.assertEqual(len({x["command"].lower() for x in catalog["commands"]}), 100)

    def test_security_guards(self):
        source = (ROOT / "src/Wolf.Commands.Api/Program.cs").read_text()
        for token in ("ValidAlgorithms", "RequireAuthorization", "set_config('app.tenant_id'", "NO_HANDLER"):
            self.assertIn(token, source)

    def test_rls(self):
        for name in ("001_init.sql", "002_workspaces.sql"):
            sql = (ROOT / "db" / name).read_text().lower()
            self.assertIn("enable row level security", sql)
            self.assertIn("force row level security", sql)

    def test_ci_files(self):
        self.assertTrue((ROOT / ".github/workflows/unified-v2-1-ci.yml").is_file())
        self.assertTrue((ROOT / "tests/rls_integration.sql").is_file())

if __name__ == "__main__":
    unittest.main()
