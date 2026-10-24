"""Focused contract tests for live-transport status and response parsing."""

import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from .client import ZetarisClient, ZetarisConfig, ZetarisResult
from .lens_adapter import LensTables, read_lens_evidence, run_lens_diagnostics
from .smoke import activity_count_sql, cross_expense_sql, cross_source_sql


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class ZetarisClientTests(unittest.TestCase):
    def setUp(self):
        self.client = ZetarisClient(ZetarisConfig("https://example.invalid", "secret", "42", query_limit=50))

    def test_missing_configuration_never_falls_back(self):
        result = ZetarisClient(None).query("SELECT 1 AS one")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.rows, ())

    def test_real_transport_payload_and_rows(self):
        payload = {"headers": ["source_id", "allocated_hours"], "data": [["TS-101", 8]]}
        with patch("zetaris.client.urlopen", return_value=_Response(json.dumps(payload).encode())) as send:
            result = self.client.query("SELECT source_id FROM LENS.timesheets")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.rows[0]["source_id"], "TS-101")
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.invalid/api/proxy/sql-editor/sqls/run-query")
        self.assertEqual(json.loads(request.data), {"sql": "SELECT source_id FROM LENS.timesheets", "limit": 50})
        self.assertEqual(request.get_header("X-org-id"), "42")
        self.assertTrue(request.get_header("Authorization").startswith("Bearer "))
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(request.get_header("X-request-id"))

    def test_official_positional_rows_are_preserved(self):
        with patch("zetaris.client.urlopen", return_value=_Response(b'{"data":[["1"]]}')):
            result = self.client.query("SELECT 1 AS one")
        self.assertEqual(result.rows, (("1",),))

    def test_engine_id_and_config_validation(self):
        client = ZetarisClient(ZetarisConfig("http://localhost:3000", "key", "7", engine_id="eng-1"))
        with patch("zetaris.client.urlopen", return_value=_Response(b'{"data":[]}')) as send:
            client.query("SHOW LIGHTNING DATABASES")
        self.assertEqual(json.loads(send.call_args.args[0].data)["engineId"], "eng-1")
        for url in ("https://example.invalid/api/v1.0", "http://example.invalid", "https://user:pass@example.invalid"):
            with self.assertRaises(ValueError):
                ZetarisConfig(url, "key", "7").validate()
        with self.assertRaises(ValueError):
            ZetarisConfig("https://example.invalid", "key", "org-name").validate()
        with patch.dict(os.environ, {"ZETARIS_BASE_URL": "https://example.invalid", "ZETARIS_API_KEY": "key", "ZETARIS_ORG_ID": "7", "ZETARIS_QUERY_LIMIT": "0"}):
            with self.assertRaises(ValueError):
                ZetarisConfig.from_environment()

    def test_write_sql_is_refused_before_transport(self):
        with patch("zetaris.client.urlopen") as send:
            for sql in ("DROP TABLE X", "SELECT 1; DELETE FROM X", "SELECT 1 INTO X"):
                self.assertEqual(self.client.query(sql).status, "error")
        send.assert_not_called()

    def test_grant_column_is_valid_in_read_only_select(self):
        with patch("zetaris.client.urlopen", return_value=_Response(b'{"data":[]}')) as send:
            result = self.client.query("SELECT claim_id, grant FROM LENS.report_a")
        self.assertEqual(result.status, "ok")
        send.assert_called_once()

    def test_failures_are_explicit_and_do_not_echo_secrets(self):
        with patch("zetaris.client.urlopen", side_effect=URLError("secret unreachable")):
            result = self.client.query("SELECT 1 AS one")
        self.assertEqual(result.status, "unavailable")
        self.assertNotIn("secret", result.message)
        with patch("zetaris.client.urlopen", side_effect=HTTPError("https://example.invalid", 401, "secret", {}, None)):
            result = self.client.query("SELECT 1 AS one")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.message, "Zetaris HTTP 401")

    def test_cross_source_sql_uses_canonical_ids_and_both_reports(self):
        query = cross_source_sql("LENS.timesheets", "LENS.report_a", "LENS.report_b")
        self.assertIn("t.source_id = c.source_id", query)
        self.assertIn("UNION ALL", query)
        self.assertIn("SUM(c.quantity)", query)
        with self.assertRaises(ValueError):
            cross_source_sql("LENS.timesheets; DROP TABLE X", "LENS.report_a", "LENS.report_b")
        expense = cross_expense_sql("LENS.receipts", "LENS.report_a", "LENS.report_b")
        self.assertIn("r.source_id = c.source_id", expense)
        self.assertIn("kind = 'expense'", expense)
        self.assertIn("SUM(c.quantity)", expense)
        self.assertEqual(activity_count_sql("LENS.activity_log"), "SELECT COUNT(*) AS activity_records FROM LENS.activity_log")

    def test_lens_diagnostics_preserve_query_rows_but_forbid_review_use(self):
        class Client:
            def __init__(self):
                self.sql = []
                self.results = iter((
                    ZetarisResult("ok", (("TS-101", "4", "8", "2"),), request_id="staff"),
                    ZetarisResult("ok", (("RC-201", "120", "120", "2"),), request_id="expense"),
                    ZetarisResult("ok", (("8",),), request_id="activity"),
                ))

            def query(self, sql):
                self.sql.append(sql)
                return next(self.results)

        client = Client()
        tables = LensTables("LENS.timesheets", "LENS.receipts", "LENS.activity_log", "LENS.report_a", "LENS.report_b")
        result = run_lens_diagnostics(client, tables)
        self.assertEqual(result["status"], "ok")
        self.assertIs(result["review_eligible"], False)
        self.assertTrue(any("omit claims" in item for item in result["limitations"]))
        self.assertEqual(result["rows"]["staff_time"][0]["allocated_hours"], "8")
        self.assertEqual(result["rows"]["expenses"][0]["source_id"], "RC-201")
        self.assertEqual(result["rows"]["activities"][0]["activity_records"], "8")
        self.assertEqual(result["request_ids"], {"staff_time": "staff", "expenses": "expense", "activities": "activity"})
        self.assertEqual(len(client.sql), 3)
        with self.assertRaisesRegex(RuntimeError, "not review evidence"):
            read_lens_evidence(client, tables)

    def test_lens_adapter_fails_closed_on_missing_query_columns(self):
        class Client:
            def query(self, _sql):
                return ZetarisResult("ok", ({"source_id": "TS-101"},), request_id="x")

        tables = LensTables("LENS.timesheets", "LENS.receipts", "LENS.activity_log", "LENS.report_a", "LENS.report_b")
        result = run_lens_diagnostics(Client(), tables)
        self.assertEqual(result["status"], "error")
        self.assertIs(result["review_eligible"], False)
        self.assertIn("required evidence column", result["message"])


if __name__ == "__main__":
    unittest.main()
