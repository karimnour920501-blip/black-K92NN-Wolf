from pathlib import Path
import json

root = Path(__file__).resolve().parent
commands = json.loads((root / "src/Wolf.Commands.Api/commands.json").read_text())["commands"]
assert len(commands) == 100
assert len({x["command"].lower() for x in commands}) == 100
source = (root / "src/Wolf.Commands.Api/Program.cs").read_text()
for guard in ("ValidAlgorithms", "RequireAuthorization", "set_config('app.tenant_id'", "NO_HANDLER"):
    assert guard in source, guard
print("PASS: static source contracts (NOT runtime integration)")
