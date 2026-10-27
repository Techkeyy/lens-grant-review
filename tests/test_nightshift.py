"""Nightshift decisions can select only a supported, already open question."""

import io
import json
import unittest
from unittest.mock import patch

from lens_investigator import choose_probe
from nightshift import _base_url, choose_followup


FINDINGS = [
    {"code": "OVERALLOCATED_SOURCE", "status": "needs_correction", "arithmetic": {"allocated_total": "8", "source_total": "4"}},
    {"code": "ACTIVITY_SUPPORT_GAP", "status": "needs_evidence", "arithmetic": {"reported": "10", "linked_distinct_records": 8}},
]


class NightshiftTests(unittest.TestCase):
    def test_url_normalization(self):
        self.assertEqual(_base_url("127.0.0.1:8088/v1/models"), "http://127.0.0.1:8088/v1")
        self.assertEqual(_base_url("https://example.org/v1/chat/completions"), "https://example.org/v1")
        with self.assertRaises(ValueError):
            _base_url("http://example.org/v1")

    @patch.dict("os.environ", {}, clear=True)
    def test_no_runtime_is_explicit(self):
        self.assertEqual(choose_followup(FINDINGS)["status"], "not_configured")

    @patch.dict("os.environ", {"NIGHTSHIFT_BASE_URL": "127.0.0.1:8088", "NIGHTSHIFT_RUNTIME_TOKEN": "real-test-token"}, clear=True)
    @patch("nightshift.request.urlopen")
    def test_model_can_prioritize_existing_gap(self, urlopen):
        payload = {"id": "req-123", "model": "meterless/auto", "choices": [{"message": {"content": json.dumps({"selected_code": "ACTIVITY_SUPPORT_GAP"})}}]}
        urlopen.side_effect = [io.BytesIO(b'{"data":[{"id":"meterless/auto"}]}'),
                               io.BytesIO(json.dumps(payload).encode())]
        outcome = choose_followup(FINDINGS)
        self.assertEqual(outcome["status"], "used")
        self.assertEqual(outcome["selected_code"], "ACTIVITY_SUPPORT_GAP")
        self.assertEqual(choose_probe(FINDINGS, outcome["selected_code"])[0]["code"], "ACTIVITY_SUPPORT_GAP")
        req = urlopen.call_args.args[0]
        self.assertEqual(req.get_header("Authorization"), "Bearer real-test-token")
        self.assertEqual(req.get_header("Meterless-app"), "lens")

    @patch.dict("os.environ", {"NIGHTSHIFT_BASE_URL": "127.0.0.1:8088", "NIGHTSHIFT_RUNTIME_TOKEN": "real-test-token"}, clear=True)
    @patch("nightshift.request.urlopen")
    def test_unsupported_model_choice_falls_back(self, urlopen):
        payload = {"choices": [{"message": {"content": json.dumps({"selected_code": "CLEAR_ALL"})}}]}
        urlopen.side_effect = [io.BytesIO(b'{"data":[{"id":"meterless/auto"}]}'),
                               io.BytesIO(json.dumps(payload).encode())]
        outcome = choose_followup(FINDINGS)
        self.assertEqual(outcome["status"], "unavailable")
        self.assertIsNone(outcome["selected_code"])
        self.assertEqual(choose_probe(FINDINGS)[0]["code"], "OVERALLOCATED_SOURCE")


if __name__ == "__main__":
    unittest.main()
