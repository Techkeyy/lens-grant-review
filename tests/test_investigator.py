"""Focused tests for conditional, bounded evidence rereads."""

import unittest

from lens_investigator import investigate
from zetaris.client import ZetarisResult
from zetaris.test_raw_evidence import FixtureClient, TABLES
from zetaris.raw_evidence import read_lens_snapshot


def finding(code, key="issue:one"):
    return {"code": code, "key": key, "status": "needs_correction",
            "claims": [{"id": "A-TIME-1", "file": "reading_futures_draft.csv", "row": 2}],
            "sources": [{"id": "TS-101", "file": "timesheets.csv", "row": 2}]}


class InvestigatorTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = read_lens_snapshot(FixtureClient(), TABLES)
        self.zetaris = {"manifest": self.snapshot["manifest"]}

    def test_overallocation_selects_three_sources_and_activity_is_next_branch(self):
        client = FixtureClient()
        findings = [finding("ACTIVITY_SUPPORT_GAP", "gap"), finding("OVERALLOCATED_SOURCE", "hours")]
        probe = investigate(findings, self.zetaris, client, TABLES)
        self.assertEqual(probe["code"], "OVERALLOCATED_SOURCE")
        self.assertEqual(probe["status"], "confirmed_against_snapshot")
        self.assertEqual(probe["tables"], [TABLES.timesheets, TABLES.report_a, TABLES.report_b])
        self.assertEqual(len(client.calls), 3)
        self.assertTrue(all("SELECT " in sql and " ORDER BY " in sql and " LIMIT " in sql for sql in client.calls))
        # A local correction changes the next finding, not the imported Zetaris rows.
        client = FixtureClient()
        probe = investigate([findings[0]], self.zetaris, client, TABLES)
        self.assertEqual(probe["code"], "ACTIVITY_SUPPORT_GAP")
        self.assertEqual(probe["status"], "confirmed_against_snapshot")
        self.assertEqual(probe["tables"], [TABLES.activity])
        self.assertEqual(len(client.calls), 1)

    def test_changed_table_abstains_without_rewriting_finding(self):
        client = FixtureClient()
        client.rows[TABLES.timesheets][0]["hours"] = "5"
        issue = finding("OVERALLOCATED_SOURCE")
        probe = investigate([issue], self.zetaris, client, TABLES)
        self.assertEqual(probe["status"], "stale")
        self.assertIn("reimport", probe["observation"])
        self.assertEqual(issue["code"], "OVERALLOCATED_SOURCE")
        self.assertEqual(len(client.calls), 1)

    def test_query_failure_is_generic_and_does_not_expose_secret(self):
        class FailedClient(FixtureClient):
            def query(self, sql):
                self.calls.append(sql)
                return ZetarisResult("error", message="secret=must-not-appear", request_id="request-1")

        probe = investigate([finding("ACTIVITY_SUPPORT_GAP")], self.zetaris, FailedClient(), TABLES)
        self.assertEqual(probe["status"], "unavailable")
        self.assertEqual(probe["request_ids"], ["request-1"])
        self.assertNotIn("must-not-appear", str(probe))

    def test_local_review_makes_no_live_claim_or_query(self):
        probe = investigate([finding("OVERALLOCATED_SOURCE")], None)
        self.assertEqual(probe["status"], "snapshot_only")
        self.assertEqual(probe["tables"], [])
        self.assertEqual(probe["request_ids"], [])


if __name__ == "__main__":
    unittest.main()
