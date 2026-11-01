#!/usr/bin/env python3
"""Reconstruction provenance/evidence policy (not a release certifier)."""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "rebuild" / "EVIDENCE.json"
REQUIRED = {
    "python_web_mock", "js_web_mock", "pyright", "mobile_s1_source",
    "mobile_s6_source", "mobile_s6_gate_tests", "mobile_s6_typecheck",
    "mobile_s6_ast_lint", "mobile_s6_metro", "mobile_s6_dependency_audit",
    "openai_live", "native_android_build", "native_ios_build",
    "mobile_s6_device_e2e", "mobile_jwt_rbac_tenant",
    "mobile_accessibility_qa", "mobile_zero_critical",
}
URL_PREFIX = "https://github.com/karimnour920501-blip/black-K92NN-Wolf/"
COMPLETED = {"passed", "passed-limited", "passed-non-native"}


def validate_manifest(value):
    problems = []
    if not isinstance(value, dict):
        return ["Manifest is not a JSON object"]
    if value.get("schema_version") != 1 or value.get("system") != "BLACK-K92N-WOLF":
        problems.append("Invalid schema/version/system")
    evidence = value.get("verification", {})
    if not isinstance(evidence, dict):
        return problems + ["Missing verification dictionary"]
    missing = REQUIRED - evidence.keys()
    if missing:
        problems.append("Missing evidence keys: " + ", ".join(sorted(missing)))
    for key, item in evidence.items():
        if not isinstance(item, dict) or not isinstance(item.get("status"), str):
            problems.append(key + ": invalid evidence entry")
            continue
        refs = item.get("evidence", [])
        if not isinstance(refs, list):
            problems.append(key + ": evidence must be list")
            continue
        if item["status"] in COMPLETED and not refs:
            problems.append(key + ": passed without linked evidence")
        for ref in refs:
            if not isinstance(ref, str) or not ref.startswith(URL_PREFIX):
                problems.append(key + ": unsafe or non-project evidence URL")
    if value.get("production_ready") is not False:
        problems.append("Production flag must remain false until separate release approval")
    approvals = value.get("approvals", {})
    if not isinstance(approvals, dict) or any(approvals.values()):
        problems.append("This inventory has no permission for privileged actions")
    if value.get("web_ui", {}).get("copied_to_rebuild_branch") is not False:
        problems.append("Missing index.html must be explicitly acknowledged")
    if evidence.get("openai_live", {}).get("status") != "failed-authentication":
        problems.append("OpenAI HTTP 401 must not be rewritten as verified")
    if evidence.get("mobile_s6_dependency_audit", {}).get("status") != "failed":
        problems.append("The S6 security scan blocker must remain reported")
    if evidence.get("mobile_s6_device_e2e", {}).get("count_verified") != 0:
        problems.append("No real dual-platform E2E execution evidenced")
    return problems


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    target = pathlib.Path(args[0]) if args else EVIDENCE
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("INVENTORY FAIL: missing or invalid JSON", file=sys.stderr)
        return 1
    errors = validate_manifest(value)
    if errors:
        print("RECONSTRUCTION INVENTORY FAIL", file=sys.stderr)
        for x in errors:
            print("- " + x, file=sys.stderr)
        return 1
    print("RECONSTRUCTION INVENTORY VALID: provenance and blockers reported.")
    print("RELEASE BLOCKED: no production, native E2E, or OpenAI-live approval.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
