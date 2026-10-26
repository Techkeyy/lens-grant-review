"""HTTP ownership and persistence checks for saved reviews."""

import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import accounts
import app

REAL_AUTHENTICATE = accounts.authenticate


class SavedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db, self.previous_store = app.DB, app.METERLESS_STORE
        app.DB = Path(self.temp.name) / "lens.sqlite3"
        app.METERLESS_STORE = Path(self.temp.name) / "meterless"
        self.auth_patch = patch("app.accounts.authenticate", side_effect=lambda value: {
            "id": value.removeprefix("Bearer "), "email": None} if value in ("Bearer alice", "Bearer bob") else
            (_ for _ in ()).throw(accounts.Unauthorized("Sign in to access reviews")))
        self.auth_patch.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.auth_patch.stop()
        app.DB, app.METERLESS_STORE = self.previous_db, self.previous_store
        self.temp.cleanup()

    def call(self, owner, method, path, data=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        body = json.dumps(data).encode() if data is not None else None
        conn.request(method, path, body, {"Authorization": f"Bearer {owner}", "Content-Type": "application/json"})
        response = conn.getresponse()
        result = json.loads(response.read())
        status = response.status
        conn.close()
        return status, result

    def test_each_account_has_separate_saved_reviews_and_history(self):
        status, data = self.call("alice", "POST", "/api/reviews", {"title": "First grant"})
        self.assertEqual(status, 201, data)
        first = data["review"]["id"]
        status, data = self.call("alice", "POST", "/api/reviews", {"title": "Second grant"})
        self.assertEqual(status, 201, data)
        second = data["review"]["id"]
        status, data = self.call("bob", "POST", "/api/reviews", {"title": "Bob's grant"})
        self.assertEqual(status, 201, data)
        bob = data["review"]["id"]
        self.assertEqual(len(self.call("alice", "GET", "/api/reviews")[1]["reviews"]), 2)
        self.assertEqual(len(self.call("bob", "GET", "/api/reviews")[1]["reviews"]), 1)
        status, state = self.call("alice", "POST", "/api/sample", {"review_id": first})
        self.assertEqual(status, 200, state)
        self.assertEqual(state["phase"], "imported")
        status, state = self.call("alice", "GET", f"/api/state?review_id={first}")
        self.assertEqual(status, 200, state)
        self.assertEqual(state["meterless"]["status"], "live")
        self.assertGreater(state["meterless"]["event_count"], 0)
        self.assertEqual(self.call("alice", "GET", f"/api/state?review_id={second}")[1]["phase"], "empty")
        self.assertEqual(self.call("bob", "GET", f"/api/state?review_id={bob}")[1]["phase"], "empty")
        for method, route, payload in (("GET", f"/api/state?review_id={first}", None),
                                       ("GET", f"/api/export?review_id={first}", None),
                                       ("POST", "/api/check", {"review_id": first}),
                                       ("POST", "/api/sample", {"review_id": first})):
            status, response = self.call("bob", method, route, payload)
            self.assertEqual(status, 404, response)
        self.assertEqual(self.call("bob", "GET", "/api/reviews")[1]["reviews"][0]["id"], bob)

    def test_rejects_stale_writes(self):
        review = accounts.create_review("local", "Concurrent", app.DB)
        row = accounts.read_review("local", review["id"], app.DB)
        accounts.save_review("local", review["id"], {"phase": "imported"}, row["row_version"], None, app.DB)
        with self.assertRaises(accounts.Conflict):
            accounts.save_review("local", review["id"], {"phase": "empty"}, row["row_version"], None, app.DB)

    def test_public_routes_require_auth_and_review_id(self):
        self.auth_patch.stop()
        self.auth_patch = patch("app.accounts.authenticate", side_effect=lambda value: (
            {"id": "alice", "email": None} if value == "Bearer alice" else
            (_ for _ in ()).throw(accounts.Unauthorized("Sign in to access reviews"))))
        self.auth_patch.start()
        with patch("app.accounts.public_mode", return_value=True):
            self.assertEqual(self.call("missing", "GET", "/api/reviews")[0], 401)
            self.assertEqual(self.call("alice", "GET", "/api/state")[0], 400)
            self.assertEqual(self.call("alice", "POST", "/api/sample", {})[0], 400)

    def test_supabase_row_keeps_meterless_events_and_enforces_owner_and_version(self):
        rows = {}

        def fake_request(url, method="GET", payload=None, headers=None):
            parts = urlparse(url)
            query = parse_qs(parts.query)
            if parts.path.endswith("/auth/v1/user"):
                return {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "email": "a@example.test"}
            if method == "POST":
                rows[payload["id"]] = dict(payload)
                return [dict(payload)]
            review_id = query.get("id", [""])[0].removeprefix("eq.")
            owner = query.get("owner_id", [""])[0].removeprefix("eq.")
            row = rows.get(review_id)
            if row is None or row["owner_id"] != owner:
                return []
            if method == "PATCH":
                expected = int(query["row_version"][0].removeprefix("eq."))
                if expected != row["row_version"]:
                    return []
                row.update(payload)
            return [dict(row)]

        with patch("accounts.public_mode", return_value=True), \
             patch("accounts._settings", return_value=("https://example.supabase.co", "anon", "service")), \
             patch("accounts._request", side_effect=fake_request):
            user = REAL_AUTHENTICATE("Bearer valid-token")
            review = accounts.create_review(user["id"], "Stored", app.DB)
            review_id = review["id"]
            state = {"phase": "checked", "namespace": "lensabc", "revision": 1}
            events = {"events": [{"id": "evt_1"}], "audit": []}
            accounts.save_review(user["id"], review_id, state, 0, events, app.DB)
            restored = accounts.read_review(user["id"], review_id, app.DB)
            self.assertEqual(restored["state"], state)
            self.assertEqual(restored["meterless_data"], events)
            self.assertEqual(restored["row_version"], 1)
            with self.assertRaises(accounts.NotFound):
                accounts.read_review("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", review_id, app.DB)
            with self.assertRaises(accounts.Conflict):
                accounts.save_review(user["id"], review_id, {}, 0, None, app.DB)

    def test_public_binding_without_auth_configuration_fails_closed(self):
        environment = dict(os.environ)
        for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
            environment.pop(key, None)
        environment["PORT"] = "0"
        environment["LENS_HOST"] = "0.0.0.0"
        result = subprocess.run([sys.executable, "app.py"], cwd=app.ROOT,
                                env=environment, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Public binding requires configured Supabase authentication", result.stderr)

    def test_public_expensive_work_has_single_flight_and_rate_limit(self):
        owner, review_id = "rate-test", "one-review"
        with patch("app.time.monotonic", return_value=1000):
            self.assertIsNone(app.claim_public_action(owner, review_id))
            self.assertEqual(app.claim_public_action(owner, review_id), 409)
            app.release_public_action(owner, review_id)
            for _ in range(app.MAX_PUBLIC_ACTIONS_PER_USER - 1):
                self.assertIsNone(app.claim_public_action(owner, review_id))
                app.release_public_action(owner, review_id)
            self.assertEqual(app.claim_public_action(owner, review_id), 429)
        with patch("app.time.monotonic", return_value=1000 + app.PUBLIC_ACTION_WINDOW_SECONDS + 1):
            self.assertIsNone(app.claim_public_action(owner, review_id))
            app.release_public_action(owner, review_id)

    def test_public_storage_caps_and_subprocess_slot(self):
        files = {name: (app.ROOT / "examples" / name).read_text(encoding="utf-8") for name in app.REQUIRED}
        with patch("app.accounts.public_mode", return_value=True):
            app.enforce_public_import_limits(files)
            oversized = dict(files)
            oversized["timesheets.csv"] = "x" * (app.MAX_PUBLIC_IMPORT_BYTES + 1)
            with self.assertRaises(accounts.PayloadTooLarge):
                app.enforce_public_import_limits(oversized)
            too_many_rows = dict(files)
            too_many_rows["timesheets.csv"] = "source_id,person,date,hours,project_note\n" + "a,b,c,d,e\n" * 201
            with self.assertRaises(accounts.PayloadTooLarge):
                app.enforce_public_import_limits(too_many_rows)
            context = {"owner": "alice", "id": "a", "state": {}, "version": 0,
                       "meterless_data": {"events": "x" * app.MAX_PUBLIC_SAVED_BYTES}}
            token = app.REQUEST_REVIEW.set(context)
            try:
                with self.assertRaises(accounts.PayloadTooLarge):
                    app.save_state({"phase": "checked"})
            finally:
                app.REQUEST_REVIEW.reset(token)
            app.METERLESS_GATE.acquire()
            try:
                with self.assertRaises(accounts.Busy):
                    app.meterless("audit", {}, "lensbusy")
            finally:
                app.METERLESS_GATE.release()

    def test_browser_roles_have_no_direct_review_table_policy(self):
        sql = (app.ROOT / "docs" / "lens_reviews.sql").read_text(encoding="utf-8").lower()
        self.assertIn("revoke all on table public.lens_reviews from anon, authenticated", sql)
        self.assertNotIn("create policy", sql)


if __name__ == "__main__":
    unittest.main()
