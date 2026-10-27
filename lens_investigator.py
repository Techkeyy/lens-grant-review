"""One bounded, evidence-driven follow-up for a completed Lens review.

The planner chooses a probe from checked findings. It cannot invent SQL,
change a finding, link a source, or treat a failed reread as confirmation.
"""

from __future__ import annotations

import csv
from hashlib import sha256
import io

from zetaris.lens_adapter import _as_records
from zetaris.raw_evidence import SPECS


PROBES = {
    "OVERALLOCATED_SOURCE": {
        "files": ("timesheets.csv", "reading_futures_draft.csv", "community_learning_draft.csv"),
        "reason": "Two draft allocations exceed one recorded timesheet; inspect their original rows together.",
        "question": "Which report allocation should the reviewer correct or explain against this timesheet?",
    },
    "ACTIVITY_SUPPORT_GAP": {
        "files": ("activity_log.csv",),
        "reason": "The report claims more sessions than its linked activity records support; inspect the activity register.",
        "question": "Can the reviewer supply the missing session records or explain the difference?",
    },
}


def choose_probe(findings: list[dict], preferred_code: str | None = None) -> tuple[dict, dict] | None:
    """Choose at most one open finding; branch priority is stable on reruns."""
    order = ([preferred_code] if preferred_code in PROBES else []) + [code for code in PROBES if code != preferred_code]
    for code in order:
        for finding in findings:
            if finding["code"] == code and finding["status"] != "clear":
                return finding, PROBES[code]
    return None


def _captured_sha(rows: list[dict], columns: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows({column: "" if row[column] is None else str(row[column]) for column in columns} for row in rows)
    return sha256(output.getvalue().encode("utf-8")).hexdigest()


def investigate(findings: list[dict], zetaris: dict | None, client=None, tables=None,
                preferred_code: str | None = None) -> dict | None:
    """Reread only selected tables and compare them with the *imported* snapshot.

    The imported hashes are independent of subsequent local reviewer edits.
    Each reread is bounded by the configured query limit. The result remains
    advisory; the original deterministic findings are never rewritten.
    """
    selection = choose_probe(findings, preferred_code)
    if selection is None:
        return None
    finding, plan = selection
    files = plan["files"]
    probe = {"finding_key": finding["key"], "code": finding["code"],
             "reason": plan["reason"], "question": plan["question"],
             "files": list(files), "tables": [], "request_ids": [],
             "refs": finding["claims"] + finding["sources"]}
    if zetaris is None:
        probe.update(status="snapshot_only", observation="Used the uploaded CSV rows; no live Zetaris follow-up was attempted.")
        return probe
    if client is None or client.config is None or tables is None:
        probe.update(status="unavailable", observation="Zetaris follow-up was unavailable; the captured import remains the review basis.")
        return probe
    by_file = {item[0]: item for item in SPECS}
    for filename in files:
        entry = zetaris["manifest"].get(filename)
        if not entry:
            probe.update(status="unavailable", observation="The captured table manifest is incomplete; follow-up could not be verified.")
            return probe
        _name, attribute, key, columns = by_file[filename]
        table = getattr(tables, attribute)  # LensTables validates every identifier.
        if entry["table"] != table:
            probe.update(status="stale", observation="The registered table differs from the imported source; reimport before following up.")
            return probe
        probe["tables"].append(table)
        if entry["row_count"] > client.config.query_limit:
            probe.update(status="unavailable", observation="A selected table exceeds the configured follow-up row limit.")
            return probe
        result = client.query(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {key} LIMIT {client.config.query_limit}")
        if result.request_id:
            probe["request_ids"].append(result.request_id)
        if result.status != "ok":
            probe.update(status="unavailable", observation="A Zetaris follow-up query failed; no live confirmation was made.")
            return probe
        try:
            rows = _as_records(result, columns)
            keys = [str(row[key]).strip() for row in rows]
            if (len(rows) != entry["row_count"] or any(not item for item in keys)
                    or len(set(keys)) != len(keys) or set(keys) != set(entry["keys"])
                    or any(any(isinstance(row[column], (list, dict)) for column in columns) for row in rows)):
                raise ValueError("Rows or source IDs differ from the imported snapshot")
            current_sha = _captured_sha(rows, columns)
        except (ValueError, KeyError, TypeError):
            probe.update(status="stale", observation="A selected table no longer matches the imported rows; reimport before relying on the follow-up.")
            return probe
        if current_sha != entry["snapshot_sha256"]:
            probe.update(status="stale", observation="A selected table changed after import; reimport before relying on the follow-up.")
            return probe
    probe.update(status="confirmed_against_snapshot",
                 observation="Selected Zetaris tables still match the identified rows captured at import. This is a reread, not a transactionally frozen source.")
    return probe
