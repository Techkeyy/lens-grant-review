"""Read a complete, identified five-table Lens snapshot from Zetaris.

The query results are not treated as evidence when any table fails, is empty,
is truncated, has a duplicate ID, or changes count while being read.
"""

from __future__ import annotations

import csv
from hashlib import sha256
import io
from typing import Any

from .client import ZetarisClient, ZetarisResult
from .lens_adapter import LensTables, _as_records


SPECS = (
    ("timesheets.csv", "timesheets", "source_id", ("source_id", "person", "date", "hours", "project_note")),
    ("receipts.csv", "receipts", "source_id", ("source_id", "vendor", "date", "amount_usd", "description")),
    ("activity_log.csv", "activity", "source_id", ("source_id", "date", "activity")),
    ("reading_futures_draft.csv", "report_a", "claim_id", ("claim_id", "grant", "kind", "source_id", "quantity", "unit", "description")),
    ("community_learning_draft.csv", "report_b", "claim_id", ("claim_id", "grant", "kind", "source_id", "quantity", "unit", "description")),
)


def _one_count(result: ZetarisResult) -> int:
    records = _as_records(result, ("row_count",))
    if len(records) != 1:
        raise ValueError("Zetaris count query did not return exactly one row")
    try:
        value = int(records[0]["row_count"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Zetaris count is not an integer") from exc
    if value < 1:
        raise ValueError("Zetaris evidence table is empty")
    return value


def read_lens_snapshot(client: ZetarisClient, tables: LensTables) -> dict[str, Any]:
    """Return exact row snapshots and provenance only after all five reads pass.

    Counts before and after are a drift check, not a transaction or remote
    version. The manifest hashes captured query rows. Users must keep source
    tables stable for the duration of an import.
    """
    limit = client.config.query_limit if client.config else 0
    if limit < 1:
        return {"status": "unavailable", "message": "Zetaris query limit is unavailable", "review_eligible": False}
    files: dict[str, str] = {}
    manifest: dict[str, dict[str, Any]] = {}
    request_ids: dict[str, list[str]] = {}
    for filename, attribute, key, columns in SPECS:
        table = getattr(tables, attribute)
        requests: list[str] = []
        request_ids[filename] = requests
        first = client.query(f"SELECT COUNT(*) AS row_count FROM {table}")
        requests.append(first.request_id)
        if first.status != "ok":
            return {"status": first.status, "message": f"{table}: {first.message}", "review_eligible": False, "request_ids": request_ids}
        try:
            count = _one_count(first)
            if count > limit:
                raise ValueError(f"{table} has {count} rows, exceeding the configured {limit} row limit")
        except ValueError as exc:
            return {"status": "error", "message": str(exc), "review_eligible": False, "request_ids": request_ids}
        selected = client.query(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {key} LIMIT {limit}")
        requests.append(selected.request_id)
        if selected.status != "ok":
            return {"status": selected.status, "message": f"{table}: {selected.message}", "review_eligible": False, "request_ids": request_ids}
        last = client.query(f"SELECT COUNT(*) AS row_count FROM {table}")
        requests.append(last.request_id)
        if last.status != "ok":
            return {"status": last.status, "message": f"{table}: {last.message}", "review_eligible": False, "request_ids": request_ids}
        try:
            rows = _as_records(selected, columns)
            if len(rows) != count or _one_count(last) != count:
                raise ValueError(f"{table}: row count changed or query returned a partial result")
            keys = [str(row[key]).strip() for row in rows]
            if any(not item for item in keys) or len(set(keys)) != len(keys):
                raise ValueError(f"{table}: missing or duplicate {key} values")
            for row in rows:
                if any(isinstance(row[column], (list, dict)) for column in columns):
                    raise ValueError(f"{table}: non-scalar value in evidence row")
            output = io.StringIO(newline="")
            writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows({column: "" if row[column] is None else str(row[column]) for column in columns} for row in rows)
            content = output.getvalue()
            if len(content.encode("utf-8")) > 2_000_000:
                raise ValueError(f"{table}: snapshot exceeds the Lens file size limit")
        except ValueError as exc:
            return {"status": "error", "message": str(exc), "review_eligible": False, "request_ids": request_ids}
        files[filename] = content
        manifest[filename] = {"table": table, "key_column": key, "keys": keys, "row_count": count,
                              "snapshot_sha256": sha256(content.encode("utf-8")).hexdigest()}
    return {"status": "ok", "review_eligible": True, "files": files, "manifest": manifest,
            "request_ids": request_ids,
            "caveat": "Captured query snapshots with count checks; Zetaris tables were not transactionally frozen."}
