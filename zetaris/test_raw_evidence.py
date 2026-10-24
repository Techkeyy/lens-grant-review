"""Verify complete row capture and fail-closed Zetaris imports."""

import csv
import io
from pathlib import Path
import unittest

from .client import ZetarisConfig, ZetarisResult
from .lens_adapter import LensTables
from .raw_evidence import SPECS, read_lens_snapshot


TABLES = LensTables("LENS_DEMO_FILES.timesheets", "LENS_DEMO_FILES.receipts", "LENS_DEMO_FILES.activity_log",
                    "LENS_DEMO_FILES.reading_futures_draft", "LENS_DEMO_FILES.community_learning_draft")


class FixtureClient:
    config = ZetarisConfig("https://example.invalid", "secret", "1", query_limit=100)

    def __init__(self, corrupt=None):
        self.corrupt = corrupt
        self.calls = []
        self.rows = {}
        root = Path(__file__).resolve().parents[1] / "examples"
        for filename, attribute, _key, _columns in SPECS:
            table = getattr(TABLES, attribute)
            with (root / filename).open(newline="", encoding="utf-8") as handle:
                self.rows[table] = list(csv.DictReader(handle))

    def query(self, sql):
        self.calls.append(sql)
        table = next((name for name in self.rows if f"FROM {name}" in sql), None)
        if table is None:
            return ZetarisResult("error", message="unknown table", request_id="r")
        if self.corrupt == "query_error" and "ORDER BY" in sql and table == TABLES.receipts:
            return ZetarisResult("error", message="registration missing", request_id="r")
        if "COUNT(*)" in sql:
            return ZetarisResult("ok", ({"row_count": len(self.rows[table])},), request_id="r")
        rows = self.rows[table]
        if self.corrupt == "partial" and table == TABLES.receipts:
            rows = rows[:-1]
        return ZetarisResult("ok", tuple(rows), request_id="r")


class RawEvidenceTests(unittest.TestCase):
    def test_complete_snapshot_is_row_identified(self):
        snapshot = read_lens_snapshot(FixtureClient(), TABLES)
        self.assertEqual(snapshot["status"], "ok")
        self.assertTrue(snapshot["review_eligible"])
        self.assertEqual(len(snapshot["request_ids"]), 5)
        self.assertEqual(snapshot["manifest"]["timesheets.csv"]["keys"], ["TS-101", "TS-102", "TS-103", "TS-104"])
        self.assertIn("B-TIME-UNCERTAIN", snapshot["files"]["community_learning_draft.csv"])
        self.assertEqual(len(list(csv.DictReader(io.StringIO(snapshot["files"]["activity_log.csv"])))), 8)

    def test_partial_table_never_returns_review_files(self):
        for fault in ("partial", "query_error"):
            result = read_lens_snapshot(FixtureClient(fault), TABLES)
            self.assertFalse(result["review_eligible"])
            self.assertNotIn("files", result)

    def test_limit_fails_before_row_query(self):
        client = FixtureClient()
        client.config = ZetarisConfig("https://example.invalid", "secret", "1", query_limit=3)
        result = read_lens_snapshot(client, TABLES)
        self.assertFalse(result["review_eligible"])
        self.assertIn("exceeding", result["message"])
        self.assertEqual(len(client.calls), 1)


if __name__ == "__main__":
    unittest.main()
