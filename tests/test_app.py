"""Exercise the same HTTP path used by a person in the local browser."""

import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path

import app
from zetaris.test_raw_evidence import FixtureClient, TABLES
from zetaris.raw_evidence import read_lens_snapshot


class AppJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db = app.DB
        self.previous_meterless_store = app.METERLESS_STORE
        app.DB = Path(self.temp.name) / "lens.sqlite3"
        app.METERLESS_STORE = Path(self.temp.name) / "meterless"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        app.DB = self.previous_db
        app.METERLESS_STORE = self.previous_meterless_store
        self.temp.cleanup()

    def call(self, method, path, data=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        body = json.dumps(data).encode() if data is not None else None
        connection.request(method, path, body, {"Content-Type": "application/json"} if body else {})
        response = connection.getresponse()
        payload = json.loads(response.read())
        status = response.status
        connection.close()
        return status, payload

    def test_zetaris_snapshot_import_reaches_findings_with_table_and_key(self):
        snapshot = read_lens_snapshot(FixtureClient(), TABLES)
        with patch("app.ZetarisConfig.from_environment", return_value=FixtureClient.config), \
             patch("app.LensTables.from_environment", return_value=TABLES), \
             patch("app.read_lens_snapshot", return_value=snapshot):
            status, state = self.call("POST", "/api/import-zetaris", {"period": {"start": "2026-07-01", "end": "2026-07-31"}})
        self.assertEqual(status, 200, state)
        self.assertEqual(state["case"]["label"], "ZETARIS QUERY SNAPSHOT")
        self.assertEqual(state["case"]["sources"][0]["ref"]["zetaris"]["table"], TABLES.timesheets)
        self.assertEqual(state["zetaris"]["manifest"]["timesheets.csv"]["row_count"], 4)
        status, state = self.call("POST", "/api/check", {})
        self.assertEqual(status, 200, state)
        finding = next(item for item in state["result"]["findings"] if item["code"] == "OVERALLOCATED_SOURCE")
        self.assertEqual(finding["sources"][0]["zetaris"]["key"], "TS-101")
        self.assertEqual(finding["sources"][0]["zetaris"]["snapshot_sha256"], snapshot["manifest"]["timesheets.csv"]["snapshot_sha256"])
        queries = [step for step in state["trace"] if step["stage"] == "zetaris_query"]
        self.assertEqual(len(queries), 5)
        self.assertEqual(queries[0]["request_ids"], snapshot["request_ids"]["timesheets.csv"])
        links = [step for step in state["trace"] if step["stage"] == "source_link"]
        self.assertTrue(any(step["claim_id"] == "B-TIME-1" and "TS-101" in step["source_ids"] for step in links))
        traced = next(step for step in state["trace"] if step.get("finding_key") == finding["key"])
        self.assertEqual(traced["meterless_id"], finding["meterless_id"])
        self.assertEqual(traced["arithmetic"], finding["arithmetic"])
        self.assertEqual(traced["refs"][-1]["zetaris"]["snapshot_sha256"], snapshot["manifest"]["timesheets.csv"]["snapshot_sha256"])
        with patch("app.ZetarisConfig.from_environment", return_value=FixtureClient.config), \
             patch("app.LensTables.from_environment", return_value=TABLES), \
             patch("app.read_lens_snapshot", return_value={"status": "error", "review_eligible": False, "message": "partial data"}):
            status, error = self.call("POST", "/api/import-zetaris", {"period": {"start": "2026-07-01", "end": "2026-07-31"}})
        self.assertEqual(status, 400)
        self.assertIn("partial data", error["error"])
        status, saved = self.call("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(saved["zetaris"]["manifest"], state["zetaris"]["manifest"])
        self.assertEqual(saved["trace"], state["trace"])

    def test_uploaded_csv_to_corrected_persisted_review(self):
        files = {name: (app.ROOT / "examples" / name).read_text(encoding="utf-8") for name in app.REQUIRED}
        status, state = self.call("POST", "/api/import", {"files": files, "period": {"start": "2026-07-01", "end": "2026-07-31"}})
        self.assertEqual(status, 200)
        self.assertEqual(state["case"]["label"], "USER UPLOADED CSV DATA")
        self.assertEqual(state["files"]["timesheets.csv"][0]["line"], 2)
        status, state = self.call("POST", "/api/check", {})
        self.assertEqual(status, 200)
        findings = state["result"]["findings"]
        conflict = next(item for item in findings if item["code"] == "OVERALLOCATED_SOURCE")
        meterless_finding_id = conflict["meterless_id"]
        self.assertEqual(conflict["arithmetic"], {"allocated_total": "8", "source_total": "4", "unit": "hours"})
        self.assertEqual(conflict["sources"][0]["file"], "timesheets.csv")
        self.assertEqual(conflict["sources"][0]["row"], 2)
        key = next(item["key"] for item in findings if item["code"] == "ACTIVITY_SUPPORT_GAP")
        status, state = self.call("POST", "/api/explain", {"key": key, "explanation": "Two session logs may be in the paper folder."})
        self.assertEqual(status, 200)
        self.assertIn(key, state["explanations"])
        status, state = self.call("POST", "/api/correct", {"claim_id": "B-TIME-1", "quantity": "0"})
        self.assertEqual(status, 200, state)
        self.assertIsNone(state["result"])
        status, state = self.call("POST", "/api/check", {})
        self.assertEqual(status, 200)
        self.assertFalse(any(item["code"] == "OVERALLOCATED_SOURCE" for item in state["result"]["findings"]))
        self.assertTrue(any(item["code"] == "ALLOCATION_WITHIN_SOURCE" and item["arithmetic"]["source_total"] == "4" for item in state["result"]["findings"]))
        status, reopened = self.call("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(reopened["corrections"][0]["from"], "4")
        self.assertEqual(reopened["corrections"][0]["to"], "0")
        self.assertEqual(reopened["explanations"][key]["text"], "Two session logs may be in the paper folder.")
        self.assertEqual(reopened["meterless"]["status"], "live")
        self.assertGreater(reopened["meterless"]["event_count"], 0)
        graph = app.meterless("read", {"findingId": meterless_finding_id}, reopened["namespace"])
        self.assertEqual(graph["finding"]["attrs"]["summary"], conflict["message"])
        self.assertTrue(graph["corrections"])
        status, export = self.call("GET", "/api/export")
        self.assertEqual(status, 200)
        self.assertEqual(export["result"], reopened["result"])

    def test_invalid_import_rejected_without_replacing_saved_review(self):
        status, original = self.call("POST", "/api/sample", {})
        self.assertEqual(status, 200)
        status, response = self.call("POST", "/api/import", {"files": {"timesheets.csv": "wrong"}, "period": {"start": "2026-07-01", "end": "2026-07-31"}})
        self.assertEqual(status, 400)
        self.assertIn("Provide all five CSVs", response["error"])
        status, saved = self.call("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(saved["file_hashes"], original["file_hashes"])

    def test_uploaded_activity_count_requires_explicit_linking(self):
        files = {name: (app.ROOT / "examples" / name).read_text(encoding="utf-8") for name in app.REQUIRED}
        status, state = self.call("POST", "/api/import", {"files": files, "period": {"start": "2026-07-01", "end": "2026-07-31"}})
        self.assertEqual(status, 200)
        claim = next(item for item in state["case"]["claims"] if item["kind"] == "activity_count")
        self.assertEqual(claim["evidence_ids"], [])
        status, state = self.call("POST", "/api/link-activities", {"claim_id": claim["id"], "evidence_ids": ["AC-301", "AC-302"]})
        self.assertEqual(status, 200)
        self.assertEqual(next(item for item in state["case"]["claims"] if item["id"] == claim["id"])["evidence_ids"], ["AC-301", "AC-302"])
        status, state = self.call("POST", "/api/check", {})
        self.assertEqual(status, 200)
        gap = next(item for item in state["result"]["findings"] if item["code"] == "ACTIVITY_SUPPORT_GAP")
        self.assertEqual(gap["arithmetic"]["gap"], "8")

    def test_meterless_failure_does_not_mark_check_complete(self):
        status, state = self.call("POST", "/api/sample", {})
        self.assertEqual(status, 200)
        with patch.object(app, "record_meterless_findings", side_effect=ValueError("Meterless runtime unavailable")):
            status, response = self.call("POST", "/api/check", {})
        self.assertEqual(status, 400)
        self.assertIn("Meterless runtime unavailable", response["error"])
        status, reopened = self.call("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(reopened["phase"], "imported")
        self.assertIsNone(reopened["result"])

    def test_explicit_report_person_survives_source_mapping(self):
        files = {name: (app.ROOT / "examples" / name).read_text(encoding="utf-8") for name in app.REQUIRED}
        name = "community_learning_draft.csv"
        lines = files[name].splitlines()
        files[name] = "\n".join([lines[0] + ",person"] + [line + (",Tari Adebayo" if line.startswith("B-TIME-UNCERTAIN,") else ",") for line in lines[1:]]) + "\n"
        status, state = self.call("POST", "/api/import", {"files": files, "period": {"start": "2026-07-01", "end": "2026-07-31"}})
        self.assertEqual(status, 200)
        status, state = self.call("POST", "/api/link-source", {"claim_id": "B-TIME-UNCERTAIN", "source_id": "TS-104"})
        self.assertEqual(status, 200)
        claim = next(item for item in state["case"]["claims"] if item["id"] == "B-TIME-UNCERTAIN")
        self.assertEqual(claim["person"], "Tari Adebayo")
        self.assertEqual(claim["identity_origin"], "report")
        status, state = self.call("POST", "/api/check", {})
        self.assertEqual(status, 200)
        self.assertTrue(any(item["code"] == "STAFF_IDENTITY_UNVERIFIED" and item["claims"][0]["id"] == "B-TIME-UNCERTAIN" for item in state["result"]["findings"]))

    def test_explicit_timesheet_project_generates_review_not_clear(self):
        files = {name: (app.ROOT / "examples" / name).read_text(encoding="utf-8") for name in app.REQUIRED}
        name = "timesheets.csv"
        lines = files[name].splitlines()
        files[name] = "\n".join([lines[0] + ",project_grant"] + [line + (",Other Program" if line.startswith("TS-102,") else ",") for line in lines[1:]]) + "\n"
        status, state = self.call("POST", "/api/import", {"files": files, "period": {"start": "2026-07-01", "end": "2026-07-31"}})
        self.assertEqual(status, 200)
        status, state = self.call("POST", "/api/check", {})
        self.assertEqual(status, 200)
        findings = state["result"]["findings"]
        self.assertTrue(any(item["code"] == "TIMESHEET_PROJECT_DIFFERS" and item["sources"][0]["id"] == "TS-102" for item in findings))
        self.assertTrue(any(item["code"] == "ALLOCATION_TOTAL_WITH_PROJECT_QUESTION" and item["arithmetic"]["source_total"] == "4" for item in findings))
        self.assertFalse(any(item["code"] == "ALLOCATION_WITHIN_SOURCE" and item["sources"][0]["id"] == "TS-102" for item in findings))


if __name__ == "__main__":
    unittest.main()
