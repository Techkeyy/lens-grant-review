import copy
import csv
import json
import unittest
from pathlib import Path

from lens_core import analyze_case


CASE = json.loads((Path(__file__).parents[1] / "examples" / "synthetic_case.json").read_text(encoding="utf-8"))


class ReconciliationTests(unittest.TestCase):
    def test_fixture_finds_overallocation_with_exact_sources(self):
        findings = analyze_case(CASE)["findings"]
        target = next(item for item in findings if item["code"] == "OVERALLOCATED_SOURCE")
        self.assertEqual(target["status"], "needs_correction")
        self.assertEqual(target["arithmetic"], {"allocated_total": "8", "source_total": "4", "unit": "hours"})
        self.assertEqual({item["id"] for item in target["claims"]}, {"A-TIME-1", "B-TIME-1"})
        self.assertEqual(target["sources"], [{"id": "TS-101", "file": "timesheets.csv", "row": 2}])

    def test_valid_proportional_time_and_expense_splits_are_clear(self):
        findings = analyze_case(CASE)["findings"]
        clear = {item["sources"][0]["id"]: item for item in findings if item["status"] == "clear"}
        self.assertEqual(clear["TS-102"]["arithmetic"]["allocated_total"], "4")
        self.assertEqual(clear["RC-201"]["arithmetic"]["allocated_total"], "120.00")

    def test_project_question_does_not_hide_cross_grant_overallocation(self):
        changed = copy.deepcopy(CASE)
        next(item for item in changed["sources"] if item["id"] == "TS-101")["project_grant"] = "Other Program"
        findings = analyze_case(changed)["findings"]
        self.assertTrue(any(item["code"] == "TIMESHEET_PROJECT_DIFFERS" for item in findings))
        conflict = next(item for item in findings if item["code"] == "OVERALLOCATED_SOURCE")
        self.assertEqual(conflict["arithmetic"]["allocated_total"], "8")

    def test_activity_gap_counts_distinct_existing_records(self):
        target = next(item for item in analyze_case(CASE)["findings"] if item["code"] == "ACTIVITY_SUPPORT_GAP")
        self.assertEqual(target["arithmetic"]["gap"], "2")
        self.assertEqual(len(target["sources"]), 8)

    def test_ambiguous_identity_is_not_assumed(self):
        target = next(item for item in analyze_case(CASE)["findings"] if item["code"] == "SOURCE_IDENTITY_UNCERTAIN")
        self.assertEqual(target["status"], "needs_review")
        self.assertEqual({item["id"] for item in target["sources"]}, {"TS-103", "TS-104"})

    def test_corrected_allocation_clears_on_rerun(self):
        corrected = copy.deepcopy(CASE)
        for claim in corrected["claims"]:
            if claim["id"] in {"A-TIME-1", "B-TIME-1"}:
                claim["quantity"] = "2"
        findings = analyze_case(corrected)["findings"]
        self.assertFalse(any(item["code"] == "OVERALLOCATED_SOURCE" for item in findings))
        self.assertTrue(any(item["status"] == "clear" and item["sources"][0]["id"] == "TS-101" for item in findings))

    def test_missing_source_never_becomes_clear(self):
        changed = copy.deepcopy(CASE)
        changed["claims"][0]["source_id"] = "UNKNOWN"
        findings = analyze_case(changed)["findings"]
        self.assertTrue(any(item["code"] == "SOURCE_IDENTITY_UNCERTAIN" and item["claims"][0]["id"] == "A-TIME-1" for item in findings))

    def test_wrong_unit_identity_and_period_never_clear(self):
        for change, code in [
            ({"unit": "EUR"}, "SOURCE_MISMATCH"),
            ({"person": "Different Person"}, "STAFF_IDENTITY_UNVERIFIED"),
        ]:
            changed = copy.deepcopy(CASE)
            changed["claims"][0].update(change)
            findings = analyze_case(changed)["findings"]
            self.assertTrue(any(item["code"] == code and item["claims"][0]["id"] == "A-TIME-1" for item in findings))
        changed = copy.deepcopy(CASE)
        changed["sources"][0]["date"] = "2026-06-30"
        findings = analyze_case(changed)["findings"]
        self.assertTrue(any(item["code"] == "SOURCE_OUTSIDE_PERIOD" and item["claims"][0]["id"] == "A-TIME-1" for item in findings))
        self.assertFalse(any(item["status"] == "clear" and item["sources"][0]["id"] == "TS-101" for item in findings if item["sources"]))

    def test_missing_activity_link_is_visible(self):
        changed = copy.deepcopy(CASE)
        claim = next(item for item in changed["claims"] if item["id"] == "A-ACT-1")
        claim["evidence_ids"].append("AC-MISSING")
        findings = analyze_case(changed)["findings"]
        target = next(item for item in findings if item["code"] == "ACTIVITY_LINKS_UNVERIFIED")
        self.assertEqual(target["arithmetic"]["missing_ids"], ["AC-MISSING"])

    def test_bad_quantity_and_missing_provenance_fail_closed(self):
        changed = copy.deepcopy(CASE)
        changed["claims"][0]["quantity"] = "-2"
        with self.assertRaises(ValueError):
            analyze_case(changed)

    def test_every_provenance_location_points_to_record_id(self):
        root = Path(__file__).parents[1] / "examples"
        for item in CASE["sources"] + CASE["claims"]:
            ref = item["ref"]
            with (root / ref["file"]).open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            self.assertGreaterEqual(len(rows), ref["row"])
            self.assertEqual(rows[ref["row"] - 1][0], item["id"])
        changed = copy.deepcopy(CASE)
        del changed["sources"][0]["ref"]
        with self.assertRaises(ValueError):
            analyze_case(changed)


if __name__ == "__main__":
    unittest.main()
