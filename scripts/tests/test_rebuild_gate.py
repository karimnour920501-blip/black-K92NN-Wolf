"""Offline tests for historical reconstruction invariant checker."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from rebuild_gate import validate_manifest

DATA = json.loads((ROOT / "docs" / "rebuild" / "EVIDENCE.json").read_text(encoding="utf-8"))


class RebuildGateTests(unittest.TestCase):
    def test_real_inventory_is_truthful_and_valid(self):
        self.assertEqual(validate_manifest(DATA), [])

    def test_cannot_fake_production_readiness(self):
        value = copy.deepcopy(DATA)
        value["production_ready"] = True
        self.assertTrue(any("Production flag" in x for x in validate_manifest(value)))

    def test_cannot_replace_failed_openai_401_with_pass(self):
        value = copy.deepcopy(DATA)
        value["verification"]["openai_live"]["status"] = "passed"
        self.assertTrue(any("401" in x for x in validate_manifest(value)))

    def test_cannot_hide_high_severity_dependency_scan(self):
        value = copy.deepcopy(DATA)
        value["verification"]["mobile_s6_dependency_audit"]["status"] = "passed"
        self.assertTrue(any("scan blocker" in x for x in validate_manifest(value)))

    def test_cannot_claim_web_ui_was_copied(self):
        value = copy.deepcopy(DATA)
        value["web_ui"]["copied_to_rebuild_branch"] = True
        self.assertTrue(any("index.html" in x for x in validate_manifest(value)))

    def test_must_provide_trusted_artifact_links_for_passed_claims(self):
        value = copy.deepcopy(DATA)
        value["verification"]["mobile_s6_source"]["evidence"] = []
        self.assertTrue(any("linked evidence" in x for x in validate_manifest(value)))
        value["verification"]["mobile_s6_source"]["evidence"] = ["https://example.com/forged"]
        self.assertTrue(any("unsafe or non-project" in x for x in validate_manifest(value)))

    def test_cannot_claim_unproven_e2e(self):
        value = copy.deepcopy(DATA)
        value["verification"]["mobile_s6_device_e2e"]["count_verified"] = 8
        self.assertTrue(any("E2E" in x for x in validate_manifest(value)))


if __name__ == "__main__":
    unittest.main()
