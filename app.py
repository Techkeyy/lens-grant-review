"""Lens review server. Local mode binds to localhost; public mode requires Auth."""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
import re
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import accounts

from lens_core import analyze_case
from lens_investigator import investigate
from zetaris import ZetarisClient, ZetarisConfig
from zetaris.lens_adapter import LensTables
from zetaris.raw_evidence import read_lens_snapshot


ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
DB = ROOT / "data" / "lens.sqlite3"
METERLESS_STORE = ROOT / "data" / "meterless"
REQUEST_REVIEW = ContextVar("request_review", default=None)
PUBLIC_ACTION_LOCK = threading.Lock()
PUBLIC_ACTIVE_REVIEWS = set()
PUBLIC_ACTION_TIMES = {}
PUBLIC_GLOBAL_TIMES = []
EXPENSIVE_ACTIONS = {"/api/sample", "/api/import", "/api/import-zetaris", "/api/check"}
MAX_PUBLIC_REVIEWS = 5
PUBLIC_ACTION_WINDOW_SECONDS = 300
MAX_PUBLIC_ACTIONS_PER_USER = 12
MAX_PUBLIC_ACTIONS_GLOBAL = 60
MAX_PUBLIC_IMPORT_BYTES = 100_000
MAX_PUBLIC_ROWS_PER_FILE = 200
MAX_PUBLIC_SAVED_BYTES = 750_000
METERLESS_GATE = threading.BoundedSemaphore(1)
ZETARIS_GATE = threading.BoundedSemaphore(1)


@contextmanager
def public_service_slot(gate, service):
    acquired = False
    if accounts.public_mode():
        acquired = gate.acquire(blocking=False)
        if not acquired:
            raise accounts.Busy(f"{service} is busy. Please try again shortly.")
    try:
        yield
    finally:
        if acquired:
            gate.release()


def claim_public_action(owner, review_id):
    """Bound work on the single free-host process; return an HTTP status on denial."""
    now = time.monotonic()
    key = (owner, review_id)
    with PUBLIC_ACTION_LOCK:
        if key in PUBLIC_ACTIVE_REVIEWS:
            return 409
        cutoff = now - PUBLIC_ACTION_WINDOW_SECONDS
        PUBLIC_GLOBAL_TIMES[:] = [instant for instant in PUBLIC_GLOBAL_TIMES if instant > cutoff]
        for user, instants in list(PUBLIC_ACTION_TIMES.items()):
            fresh = [instant for instant in instants if instant > cutoff]
            if fresh:
                PUBLIC_ACTION_TIMES[user] = fresh
            else:
                del PUBLIC_ACTION_TIMES[user]
        if (len(PUBLIC_ACTION_TIMES.get(owner, [])) >= MAX_PUBLIC_ACTIONS_PER_USER or
                len(PUBLIC_GLOBAL_TIMES) >= MAX_PUBLIC_ACTIONS_GLOBAL):
            return 429
        PUBLIC_ACTIVE_REVIEWS.add(key)
        PUBLIC_ACTION_TIMES.setdefault(owner, []).append(now)
        PUBLIC_GLOBAL_TIMES.append(now)
    return None


def release_public_action(owner, review_id):
    with PUBLIC_ACTION_LOCK:
        PUBLIC_ACTIVE_REVIEWS.discard((owner, review_id))


def enforce_public_import_limits(files):
    if not accounts.public_mode():
        return
    if not isinstance(files, dict):
        raise ValueError("Five named CSV file contents are required")
    if set(files) != set(REQUIRED) or any(not isinstance(content, str) for content in files.values()):
        raise ValueError("Upload the five required CSV files")
    if sum(len(content.encode("utf-8")) for content in files.values()) > MAX_PUBLIC_IMPORT_BYTES:
        raise accounts.PayloadTooLarge("The five CSV files must total at most 100 KB on the public demo.")
    for name, content in files.items():
        if sum(1 for _ in csv.reader(io.StringIO(content))) - 1 > MAX_PUBLIC_ROWS_PER_FILE:
            raise accounts.PayloadTooLarge(f"{name}: public demo allows at most 200 data rows")
REQUIRED = (
    "reading_futures_draft.csv",
    "community_learning_draft.csv",
    "timesheets.csv",
    "receipts.csv",
    "activity_log.csv",
)
MAX_BYTES = 2_000_000


def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL)")
    return db


def read_state():
    review = REQUEST_REVIEW.get()
    if review is not None:
        return review["state"]
    with closing(connection()) as db:
        row = db.execute("SELECT state FROM workspace WHERE id=1").fetchone()
    return json.loads(row[0]) if row else {"phase": "empty", "revision": 0}


def save_state(state):
    state["saved_at"] = datetime.now(timezone.utc).isoformat()
    review = REQUEST_REVIEW.get()
    if review is not None:
        if accounts.public_mode():
            saved_bytes = len(json.dumps({"state": state, "meterless_data": review["meterless_data"]}).encode("utf-8"))
            if saved_bytes > MAX_PUBLIC_SAVED_BYTES:
                raise accounts.PayloadTooLarge("This review has reached the public demo storage limit. Export it and start a smaller review.")
        review["version"] = accounts.save_review(review["owner"], review["id"], state,
                                                   review["version"], review["meterless_data"], DB)
        review["state"] = state
        return
    with closing(connection()) as db:
        db.execute("INSERT INTO workspace(id,state) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state", (json.dumps(state),))
        db.commit()


def meterless(action, payload, namespace):
    """Call the actual Meterless World Model bridge; never return mock success."""
    with public_service_slot(METERLESS_GATE, "Meterless"):
        return _meterless(action, payload, namespace)


def _meterless(action, payload, namespace):
    review = REQUEST_REVIEW.get()
    if review is not None and accounts.public_mode():
        with tempfile.TemporaryDirectory(prefix="lens-meterless-") as scratch:
            store = Path(scratch)
            event_file = store / ".world" / f"{namespace}.json"
            if review["meterless_data"] is not None:
                event_file.parent.mkdir(parents=True, exist_ok=True)
                event_file.write_text(json.dumps(review["meterless_data"]), encoding="utf-8")
            result = _meterless_process(action, payload, namespace, store)
            if event_file.exists():
                review["meterless_data"] = json.loads(event_file.read_text(encoding="utf-8"))
            return result
    METERLESS_STORE.mkdir(parents=True, exist_ok=True)
    return _meterless_process(action, payload, namespace, METERLESS_STORE)


def _meterless_process(action, payload, namespace, store):
    command = ["node", "--experimental-transform-types", "bridge.ts", str(store), namespace, action]
    try:
        process = subprocess.run(command, input=json.dumps(payload), text=True, capture_output=True,
                                 cwd=ROOT / "meterless", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Meterless runtime unavailable: {exc}") from exc
    try:
        response = json.loads(process.stdout)
    except ValueError as exc:
        raise ValueError("Meterless runtime returned no valid result") from exc
    if process.returncode or response.get("ok") is not True:
        raise ValueError(f"Meterless runtime error: {response.get('error', 'unknown error')}")
    return response["result"]


def meterless_source_id(state, ref):
    key = f"{ref['file']}:{ref['row']}:{ref['id']}"
    return sha256((state["namespace"] + ":" + key).encode("utf-8")).hexdigest()[:24]


def ingest_meterless(state):
    now = datetime.now(timezone.utc).isoformat()
    refs = [item["ref"] | {"id": item["id"]} for item in state["case"]["sources"] + state["case"]["claims"]]
    sources = []
    for ref in refs:
        row = next(entry["values"] for entry in state["files"][ref["file"]] if entry["line"] == ref["row"])
        source = next((item for item in state["case"]["sources"] if item["id"] == ref["id"]), None)
        kind = {"staff_time": "timesheet", "expense": "receipt", "activity": "activity"}.get(source["kind"] if source else "", "draft")
        remote = ref.get("zetaris")
        location = (f"zetaris://{remote['table']}/{remote['key']}#snapshot={remote['snapshot_sha256']}"
                    if remote else f"{ref['file']}#row={ref['row']}")
        sources.append({"id": meterless_source_id(state, ref), "kind": kind,
                        "title": ref["id"], "text": json.dumps(row, sort_keys=True),
                        "observedAt": now, "location": location})
    result = meterless("ingest", {"sources": sources}, state["namespace"])
    state["meterless"] = {"status": "live", "last_action": "ingest", "result": result}


def record_meterless_findings(state):
    now = datetime.now(timezone.utc).isoformat()
    for finding in state["result"]["findings"]:
        refs = finding["claims"] + finding["sources"]
        source_ids = list(dict.fromkeys(meterless_source_id(state, ref) for ref in refs))
        finding_id = sha256((state["namespace"] + ":" + str(state["revision"]) + ":" + finding["key"]).encode()).hexdigest()[:24]
        payload = {"id": finding_id, "sourceIds": source_ids,
                   "status": "resolved" if finding["status"] == "clear" else
                             "needs_evidence" if finding["status"] == "needs_evidence" else "needs_review",
                   "summary": finding["message"], "calculation": json.dumps(finding["arithmetic"]),
                   "observedAt": now}
        meterless("finding", payload, state["namespace"])
        finding["meterless_id"] = finding_id
    audit = meterless("audit", {}, state["namespace"])
    state["meterless"] = {"status": "live", "last_action": "findings recorded", "event_count": audit["eventCount"]}


def record_meterless_human(state, finding_id, explanation):
    result = meterless("correction", {"id": uuid.uuid4().hex, "findingId": finding_id,
                                      "actor": "grant reviewer", "explanation": explanation,
                                      "observedAt": datetime.now(timezone.utc).isoformat()}, state["namespace"])
    audit = meterless("audit", {}, state["namespace"])
    state["meterless"] = {"status": "live", "last_action": "human decision recorded", "event_count": audit["eventCount"]}
    return result


def parse_rows(filename, content):
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_BYTES:
        raise ValueError(f"{filename}: missing or over 2 MB")
    reader = csv.DictReader(io.StringIO(content, newline=""))
    if not reader.fieldnames:
        raise ValueError(f"{filename}: no header row")
    if len(reader.fieldnames) != len(set(reader.fieldnames)) or any(not field for field in reader.fieldnames):
        raise ValueError(f"{filename}: duplicate or empty header")
    rows = []
    for number, row in enumerate(reader, start=2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{filename} row {number}: malformed columns")
        if any(str(value).strip() for value in row.values()):
            rows.append({"line": number, "values": row})
    return rows


def need(row, key, filename, number):
    value = (row.get(key) or "").strip()
    if not value:
        raise ValueError(f"{filename} row {number}: {key} is required")
    return value


def build_case(files, period, allow_sample_links=False):
    missing = [name for name in REQUIRED if name not in files]
    if missing:
        raise ValueError("Provide all five CSVs: " + ", ".join(missing))
    parsed = {name: parse_rows(name, files[name]) for name in REQUIRED}
    sources, claims = [], []
    for filename, kind in (("timesheets.csv", "staff_time"), ("receipts.csv", "expense"), ("activity_log.csv", "activity")):
        for entry in parsed[filename]:
            row, line = entry["values"], entry["line"]
            source = {"id": need(row, "source_id", filename, line), "kind": kind,
                      "date": need(row, "date", filename, line), "ref": {"file": filename, "row": line}}
            if kind == "staff_time":
                source.update(person=need(row, "person", filename, line), quantity=need(row, "hours", filename, line), unit="hours")
                source["project_note"] = (row.get("project_note") or "").strip()
                explicit_project = (row.get("project_grant") or "").strip()
                if not explicit_project:
                    marked = re.fullmatch(r"\s*(?:project|program)\s*:\s*(.+?)\s*", source["project_note"], re.IGNORECASE)
                    explicit_project = marked.group(1) if marked else ""
                if explicit_project:
                    source["project_grant"] = explicit_project
            elif kind == "expense":
                source.update(vendor=need(row, "vendor", filename, line), quantity=need(row, "amount_usd", filename, line), unit="USD")
            sources.append(source)
    source_by_id = {source["id"]: source for source in sources}
    if len(source_by_id) != len(sources):
        raise ValueError("Source IDs must be unique across the three evidence files")
    activity_ids = [source["id"] for source in sources if source["kind"] == "activity"]
    for filename in REQUIRED[:2]:
        for entry in parsed[filename]:
            row, line = entry["values"], entry["line"]
            kind = need(row, "kind", filename, line)
            claim = {"id": need(row, "claim_id", filename, line), "grant": need(row, "grant", filename, line),
                     "quantity": need(row, "quantity", filename, line), "unit": need(row, "unit", filename, line),
                     "ref": {"file": filename, "row": line}}
            if kind == "activity_count":
                explicit = [key.strip() for key in (row.get("evidence_ids") or "").split(";") if key.strip()]
                linked = explicit or (activity_ids if allow_sample_links else [])
                claim.update(kind="activity_count", evidence_ids=linked,
                             evidence_link_method="explicit report IDs" if explicit else
                             "synthetic sample assumption: all uploaded activity rows" if allow_sample_links else
                             "none; user mapping required")
            elif kind in ("staff_time", "expense"):
                source_id = (row.get("source_id") or "").strip() or None
                claim.update(kind="allocation", source_id=source_id, reported_kind=kind)
                claim["source_link_method"] = "report source ID" if source_id else "no confirmed source ID"
                identity_key = "person" if kind == "staff_time" else "vendor"
                reported_identity = (row.get(identity_key) or "").strip()
                if reported_identity:
                    claim[identity_key] = reported_identity
                    claim["identity_origin"] = "report"
                if source_id and source_id in source_by_id:
                    source = source_by_id[source_id]
                    if kind != source["kind"]:
                        raise ValueError(f"{filename} row {line}: claim kind conflicts with source {source_id}")
                    # Older report CSVs name the source ID but omit person/vendor. Keep
                    # the provenance visible instead of inventing a reported identity.
                    if not reported_identity:
                        claim[identity_key] = source[identity_key]
                        claim["identity_origin"] = "linked source"
                elif not source_id:
                    description = (row.get("description") or "").lower()
                    candidates = [source for source in sources if source["kind"] == kind and
                                  source.get("person", "").split(" ")[0].lower() in description]
                    claim["candidate_source_ids"] = [source["id"] for source in candidates]
            else:
                raise ValueError(f"{filename} row {line}: unsupported kind {kind}")
            claims.append(claim)
    if len({claim["id"] for claim in claims}) != len(claims):
        raise ValueError("Claim IDs must be unique across both draft reports")
    case = {"label": "USER UPLOADED CSV DATA", "reporting_period": period, "sources": sources, "claims": claims}
    analyze_case(case)  # Validate quantities, dates, and references before saving.
    return case, parsed


def result_with_decisions(state):
    result = analyze_case(state["case"])
    for finding in result["findings"]:
        key = finding_key(finding)
        finding["key"] = key
        finding["human_explanation"] = state.get("explanations", {}).get(key)
    return result


def finding_key(finding):
    ids = ",".join(sorted(item["id"] for item in finding["claims"]))
    return f"{finding['code']}:{ids}"


def trace_step(state, stage, summary, refs=(), **details):
    """Record a completed workflow step, never an inferred agent thought."""
    state.setdefault("trace", []).append({
        "at": datetime.now(timezone.utc).isoformat(), "revision": state["revision"],
        "stage": stage, "summary": summary, "refs": list(refs), **details,
    })


def trace_import(state):
    state["trace"] = []
    if "zetaris" in state:
        for filename, entry in state["zetaris"]["manifest"].items():
            trace_step(state, "zetaris_query", "Captured a complete identified table snapshot.",
                       table=entry["table"], row_count=entry["row_count"],
                       snapshot_sha256=entry["snapshot_sha256"],
                       request_ids=state["zetaris"]["request_ids"].get(filename, []))
    else:
        trace_step(state, "local_import", "Parsed the five supplied CSV files.",
                   files={name: len(rows) for name, rows in state["files"].items()})
    trace_step(state, "meterless_ingest", "Recorded imported source and report rows in Meterless.",
               source_count=len(state["case"]["sources"]), claim_count=len(state["case"]["claims"]))


def trace_check_links(state):
    # Keep the import proof and replace the previous check's trace after a rerun.
    state["trace"] = [step for step in state.get("trace", [])
                      if step["stage"] in ("zetaris_query", "local_import", "meterless_ingest")]
    sources = {item["id"]: item for item in state["case"]["sources"]}
    for claim in state["case"]["claims"]:
        if claim["kind"] == "activity_count":
            ids = claim.get("evidence_ids", [])
            basis = claim.get("evidence_link_method", "no confirmed mapping")
        else:
            ids = [claim["source_id"]] if claim.get("source_id") else []
            basis = claim.get("source_link_method", "report source ID" if ids else "no confirmed source ID")
        refs = [claim["ref"] | {"id": claim["id"]}]
        refs.extend(sources[key]["ref"] | {"id": key} for key in ids if key in sources)
        trace_step(state, "source_link", "Read the current report-to-source mapping.", refs,
                   claim_id=claim["id"], source_ids=ids, basis=basis,
                   candidate_ids=claim.get("candidate_source_ids", []))


def trace_check_outcome(state):
    findings = state["result"]["findings"]
    for finding in findings:
        trace_step(state, "finding_recorded", "Recorded the checked finding in Meterless.",
                   finding["claims"] + finding["sources"],
                   finding_key=finding["key"], code=finding["code"], status=finding["status"],
                   arithmetic=finding["arithmetic"], meterless_id=finding["meterless_id"])


def run_investigation(state):
    """Choose one follow-up from current findings; keep failures non-authoritative."""
    client = tables = None
    if "zetaris" in state:
        try:
            config = ZetarisConfig.from_environment()
            tables = LensTables.from_environment()
            client = ZetarisClient(config)
        except ValueError:
            pass  # Persist an unavailable probe without exposing connection details.
    with public_service_slot(ZETARIS_GATE, "Zetaris"):
        probe = investigate(state["result"]["findings"], state.get("zetaris"), client, tables)
    state["investigation"] = probe
    if probe:
        summary = ("Completed one bounded Zetaris follow-up."
                   if probe["status"] == "confirmed_against_snapshot" else
                   "Attempted a bounded Zetaris follow-up; live confirmation was not possible."
                   if probe["request_ids"] else
                   "Selected a bounded follow-up without a live Zetaris query.")
        trace_step(state, "adaptive_probe", summary,
                   probe["refs"], finding_key=probe["finding_key"], code=probe["code"],
                   reason=probe["reason"], status=probe["status"], files=probe["files"],
                   tables=probe["tables"], request_ids=probe["request_ids"],
                   observation=probe["observation"], question=probe["question"])


def new_state(files, period, label):
    case, parsed = build_case(files, period, allow_sample_links=label == "SYNTHETIC DEMO DATA")
    case["label"] = label
    return {"phase": "imported", "revision": read_state().get("revision", 0) + 1,
            "case": case, "files": parsed,
            "file_hashes": {name: sha256(content.encode("utf-8")).hexdigest() for name, content in files.items()},
            "namespace": "lens" + uuid.uuid4().hex[:12],
            "explanations": {}, "corrections": [], "result": None, "checks": []}


def new_zetaris_state(snapshot, period):
    if snapshot.get("status") != "ok" or snapshot.get("review_eligible") is not True:
        raise ValueError(snapshot.get("message", "Incomplete Zetaris evidence snapshot"))
    state = new_state(snapshot["files"], period, "ZETARIS QUERY SNAPSHOT")
    state["zetaris"] = {"status": "queried", "manifest": snapshot["manifest"],
                        "request_ids": snapshot["request_ids"], "caveat": snapshot["caveat"]}
    for item in state["case"]["sources"] + state["case"]["claims"]:
        ref = item["ref"]
        manifest = snapshot["manifest"][ref["file"]]
        ref["zetaris"] = {"table": manifest["table"], "key": item["id"],
                          "snapshot_sha256": manifest["snapshot_sha256"]}
    return state


class Handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _api_error(self, exc):
        status = (401 if isinstance(exc, accounts.Unauthorized) else
                  404 if isinstance(exc, accounts.NotFound) else
                  413 if isinstance(exc, accounts.PayloadTooLarge) else
                  429 if isinstance(exc, accounts.Busy) else
                  409 if isinstance(exc, accounts.Conflict) else 503)
        self._json(status, {"error": str(exc)})

    def _load_review(self, user, review_id):
        if not review_id:
            if accounts.public_mode():
                raise ValueError("Choose a review first")
            return None
        row = accounts.read_review(user["id"], review_id, DB)
        return REQUEST_REVIEW.set({"owner": user["id"], "id": row["id"], "state": row["state"],
                                   "version": row["row_version"], "meterless_data": row.get("meterless_data")})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            try:
                return self._json(200, accounts.public_config())
            except accounts.StorageError as exc:
                return self._api_error(exc)
        if path.startswith("/api/"):
            try:
                user = accounts.authenticate(self.headers.get("Authorization"))
                if path == "/api/session":
                    demo_owner = os.environ.get("LENS_ZETARIS_DEMO_OWNER_ID")
                    can_import_zetaris = bool(demo_owner and user["id"] == demo_owner and
                                              os.environ.get("ZETARIS_API_KEY"))
                    return self._json(200, {"user": user, "can_import_zetaris": can_import_zetaris})
                if path == "/api/reviews":
                    return self._json(200, {"reviews": accounts.list_reviews(user["id"], DB)})
                review_id = parse_qs(urlparse(self.path).query).get("review_id", [None])[0]
                token = self._load_review(user, review_id)
                try:
                    return self._review_get(path)
                finally:
                    if token is not None:
                        REQUEST_REVIEW.reset(token)
            except (accounts.StorageError, ValueError) as exc:
                return self._api_error(exc) if isinstance(exc, accounts.StorageError) else self._json(400, {"error": str(exc)})
        return self._review_get(path)

    def _review_get(self, path):
        if path == "/api/state":
            state = read_state()
            if state.get("namespace"):
                try:
                    audit = meterless("audit", {}, state["namespace"])
                    state["meterless"] = {"status": "live", "last_action": "reopened", "event_count": audit["eventCount"]}
                except ValueError as exc:
                    state["meterless"] = {"status": "unavailable", "message": str(exc)}
            return self._json(200, state)
        if path == "/api/integrations":
            state = read_state()
            data_status = "captured_snapshot" if state.get("zetaris", {}).get("status") == "queried" else "not_connected_to_this_review"
            if accounts.public_mode() and REQUEST_REVIEW.get()["owner"] != os.environ.get("LENS_ZETARIS_DEMO_OWNER_ID"):
                z = {"status": "owner_demo_only", "data_query_status": data_status}
            else:
                try:
                    with public_service_slot(ZETARIS_GATE, "Zetaris"):
                        zetaris = ZetarisClient(ZetarisConfig.from_environment()).query("SELECT 1 AS one")
                    z = {"status": zetaris.status, "message": zetaris.message, "request_id": zetaris.request_id,
                         "data_query_status": data_status}
                except ValueError as exc:
                    z = {"status": "error", "message": str(exc), "data_query_status": data_status}
            if state.get("namespace"):
                try:
                    audit = meterless("audit", {}, state["namespace"])
                    m = {"status": "live", "event_count": audit["eventCount"]}
                except ValueError as exc:
                    m = {"status": "unavailable", "message": str(exc)}
            else:
                m = {"status": "not_started", "message": "Import a case to create review history"}
            return self._json(200, {"zetaris": z, "meterless": m})
        if path == "/api/export":
            state = read_state()
            if state.get("phase") != "checked":
                return self._json(409, {"error": "Run a check before exporting."})
            export = {key: state[key] for key in ("saved_at", "revision", "file_hashes", "result", "explanations", "corrections")}
            if "zetaris" in state:
                export["zetaris"] = state["zetaris"]
            export["trace"] = state.get("trace", [])
            export["investigation"] = state.get("investigation")
            return self._json(200, export)
        if path == "/vendor/supabase.js":
            target = WEB / "vendor" / "supabase.js"
        elif path in {"/fonts/fraunces-latin.woff2", "/fonts/dm-sans-latin.woff2"}:
            target = WEB / path.lstrip("/")
        elif path in {"/", "/index.html", "/app.js", "/scroll-reveal.js", "/style.css", "/hero-magnifier.png"}:
            target = WEB / ("index.html" if path == "/" else path.lstrip("/"))
        else:
            self.send_error(404)
            return
        if not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        mime = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".woff2": "font/woff2"}[target.suffix]
        self.send_response(200)
        self.send_header("Content-Type", mime if target.suffix in {".png", ".woff2"} else f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._json(404, {"error": "Unknown route"})
        try:
            user = accounts.authenticate(self.headers.get("Authorization"))
        except accounts.StorageError as exc:
            return self._api_error(exc)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            max_request = 250_000 if accounts.public_mode() else 12_000_000
            if length <= 0 or length > max_request:
                raise accounts.PayloadTooLarge("Request exceeds the public demo size limit" if accounts.public_mode() else "Request exceeds 12 MB")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            if path == "/api/reviews":
                if accounts.public_mode() and len(accounts.list_reviews(user["id"], DB)) >= MAX_PUBLIC_REVIEWS:
                    return self._json(429, {"error": "You can keep up to 5 saved reviews on this free demo."})
                review = accounts.create_review(user["id"], payload.get("title"), DB)
                return self._json(201, {"review": review})
            token = self._load_review(user, payload.get("review_id"))
            claimed = False
            active_review_id = REQUEST_REVIEW.get()["id"] if token is not None else None
            try:
                if accounts.public_mode() and path in EXPENSIVE_ACTIONS:
                    denied = claim_public_action(user["id"], active_review_id)
                    if denied:
                        message = ("This review is already processing. Wait for it to finish." if denied == 409 else
                                   "Too many imports or checks right now. Please try again in a few minutes.")
                        return self._json(denied, {"error": message})
                    claimed = True
                return self._review_post(path, payload)
            finally:
                if claimed:
                    release_public_action(user["id"], active_review_id)
                if token is not None:
                    REQUEST_REVIEW.reset(token)
        except accounts.StorageError as exc:
            self._api_error(exc)
        except (ValueError, KeyError, TypeError, AttributeError, InvalidOperation, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})

    def _review_post(self, path, payload):
        try:
            state = read_state()
            if path == "/api/sample":
                files = {name: (ROOT / "examples" / name).read_text(encoding="utf-8") for name in REQUIRED}
                enforce_public_import_limits(files)
                state = new_state(files, {"start": "2026-07-01", "end": "2026-07-31"}, "SYNTHETIC DEMO DATA")
                if REQUEST_REVIEW.get() is not None:
                    REQUEST_REVIEW.get()["meterless_data"] = None
                ingest_meterless(state)
                trace_import(state)
            elif path == "/api/import":
                files = payload.get("files")
                if not isinstance(files, dict):
                    raise ValueError("Five named CSV file contents are required")
                enforce_public_import_limits(files)
                state = new_state(files, payload.get("period"), "USER UPLOADED CSV DATA")
                if REQUEST_REVIEW.get() is not None:
                    REQUEST_REVIEW.get()["meterless_data"] = None
                ingest_meterless(state)
                trace_import(state)
            elif path == "/api/import-zetaris":
                if accounts.public_mode() and REQUEST_REVIEW.get()["owner"] != os.environ.get("LENS_ZETARIS_DEMO_OWNER_ID"):
                    return self._json(403, {"error": "Zetaris demo import is available to the demo owner only."})
                client = ZetarisClient(ZetarisConfig.from_environment())
                with public_service_slot(ZETARIS_GATE, "Zetaris"):
                    snapshot = read_lens_snapshot(client, LensTables.from_environment())
                if snapshot.get("status") == "ok":
                    enforce_public_import_limits(snapshot["files"])
                state = new_zetaris_state(snapshot, payload.get("period"))
                if REQUEST_REVIEW.get() is not None:
                    REQUEST_REVIEW.get()["meterless_data"] = None
                ingest_meterless(state)
                trace_import(state)
            elif path == "/api/check":
                if "case" not in state:
                    raise ValueError("Import records before checking")
                trace_check_links(state)
                state["result"] = result_with_decisions(state)
                trace_step(state, "reconciliation", "Ran the deterministic reconciliation rules.",
                           finding_count=len(state["result"]["findings"]),
                           finding_codes=[item["code"] for item in state["result"]["findings"]])
                run_investigation(state)
                record_meterless_findings(state)
                trace_check_outcome(state)
                state["phase"] = "checked"
                state["checks"].append({"at": datetime.now(timezone.utc).isoformat(), "revision": state["revision"],
                                        "counts": {status: sum(item["status"] == status for item in state["result"]["findings"])
                                                   for status in ("needs_correction", "needs_evidence", "needs_review", "clear")}})
            elif path == "/api/correct":
                if "case" not in state:
                    raise ValueError("Import records first")
                claim_id, quantity = payload.get("claim_id"), payload.get("quantity")
                claim = next((item for item in state["case"]["claims"] if item["id"] == claim_id), None)
                if not claim or claim["kind"] != "allocation":
                    raise ValueError("Choose an allocation claim")
                if not state.get("result"):
                    raise ValueError("Run a check before recording a correction")
                value = Decimal(str(quantity))
                if not value.is_finite() or value < 0:
                    raise ValueError("Quantity must be a nonnegative number")
                previous = claim["quantity"]
                linked = next((item for item in state["result"]["findings"] if any(ref["id"] == claim_id for ref in item["claims"]) and item["status"] != "clear"), None)
                if not linked:
                    raise ValueError("Choose an open finding for this claim")
                record_meterless_human(state, linked["meterless_id"], f"Changed {claim_id} from {previous} to {value} {claim['unit']}; rerun required")
                claim["quantity"] = str(value)
                state["corrections"].append({"claim_id": claim_id, "from": previous, "to": str(value),
                                             "at": datetime.now(timezone.utc).isoformat(), "source_revision": state["revision"]})
                state["revision"] += 1
                state["phase"] = "imported"
                state["result"] = None
            elif path == "/api/link-source":
                if "case" not in state:
                    raise ValueError("Import records first")
                claim = next((item for item in state["case"]["claims"] if item["id"] == payload.get("claim_id")), None)
                source = next((item for item in state["case"]["sources"] if item["id"] == payload.get("source_id")), None)
                if not claim or claim["kind"] != "allocation" or not source or source["kind"] != claim.get("reported_kind"):
                    raise ValueError("Choose a source of the same type as the report claim")
                claim["source_id"] = source["id"]
                claim["source_link_method"] = "user-confirmed source link"
                claim["candidate_source_ids"] = []
                key = "person" if source["kind"] == "staff_time" else "vendor"
                if not claim.get(key):
                    claim[key] = source[key]
                    claim["identity_origin"] = "user-confirmed source link"
                state["revision"] += 1
                state["phase"] = "imported"
                state["result"] = None
            elif path == "/api/link-activities":
                if "case" not in state:
                    raise ValueError("Import records first")
                claim = next((item for item in state["case"]["claims"] if item["id"] == payload.get("claim_id")), None)
                ids = payload.get("evidence_ids")
                valid_ids = {item["id"] for item in state["case"]["sources"] if item["kind"] == "activity"}
                if not claim or claim["kind"] != "activity_count" or not isinstance(ids, list) or len(ids) != len(set(ids)) or any(key not in valid_ids for key in ids):
                    raise ValueError("Choose unique IDs from the uploaded activity log")
                claim["evidence_ids"] = ids
                claim["evidence_link_method"] = "user-confirmed activity mapping"
                state["revision"] += 1
                state["phase"] = "imported"
                state["result"] = None
            elif path == "/api/explain":
                if not state.get("result"):
                    raise ValueError("Run a check before explaining")
                key = payload.get("key")
                if key not in {item["key"] for item in state["result"]["findings"]}:
                    raise ValueError("Choose a current finding")
                explanation = str(payload.get("explanation", "")).strip()
                if not explanation or len(explanation) > 2000:
                    raise ValueError("Explanation must be 1 to 2000 characters")
                finding = next(item for item in state["result"]["findings"] if item["key"] == key)
                record_meterless_human(state, finding["meterless_id"], explanation)
                state["explanations"][key] = {"text": explanation, "at": datetime.now(timezone.utc).isoformat(),
                                               "source_revision": state["revision"]}
                finding["human_explanation"] = state["explanations"][key]
            else:
                return self._json(404, {"error": "Unknown route"})
            save_state(state)
            self._json(200, state)
        except accounts.StorageError as exc:
            self._api_error(exc)
        except (ValueError, KeyError, TypeError, AttributeError, InvalidOperation, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})


if __name__ == "__main__":
    host = os.environ.get("LENS_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    public_requested = (host not in ("127.0.0.1", "localhost", "::1") or
                        "PORT" in os.environ or
                        os.environ.get("LENS_PUBLIC_MODE", "").lower() in ("1", "true", "yes") or
                        any(os.environ.get(name) for name in ("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")))
    if public_requested and not accounts.public_mode():
        raise SystemExit("Public binding requires configured Supabase authentication")
    if accounts.public_mode():
        accounts.public_config()  # Fail startup on partial credentials.
    print(f"Lens review server: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
