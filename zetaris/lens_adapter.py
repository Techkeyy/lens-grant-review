"""Diagnostic Zetaris aggregate queries. Not eligible to drive Lens findings."""

from dataclasses import dataclass
import os
import re
from typing import Any

from .client import ZetarisClient, ZetarisResult, _load_local_env
from .smoke import activity_count_sql, cross_expense_sql, cross_source_sql


_TABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class LensTables:
    timesheets: str
    receipts: str
    activity: str
    report_a: str
    report_b: str

    @classmethod
    def from_environment(cls) -> "LensTables":
        _load_local_env()
        names = ("ZETARIS_TIMESHEETS_TABLE", "ZETARIS_RECEIPTS_TABLE", "ZETARIS_ACTIVITY_TABLE",
                 "ZETARIS_REPORT_A_TABLE", "ZETARIS_REPORT_B_TABLE")
        values = [os.environ.get(name, "").strip() for name in names]
        for name, value in zip(names, values):
            if not _TABLE.fullmatch(value):
                raise ValueError(f"{name} must be a registered database.table identifier")
        return cls(*values)


def _as_records(result: ZetarisResult, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    records = []
    for row in result.rows:
        if isinstance(row, dict):
            if not all(field in row for field in fields):
                raise ValueError("Zetaris result omitted a required evidence column")
            records.append({field: row[field] for field in fields})
        elif isinstance(row, tuple) and len(row) == len(fields):
            records.append(dict(zip(fields, row)))
        else:
            raise ValueError("Zetaris result row has an unexpected shape")
    return records


LIMITATIONS = (
    "Inner joins omit claims whose source IDs have no matching timesheet or receipt.",
    "Activity count is for the whole registered table, without grant or period scope.",
    "Aggregate rows omit claim IDs, grant, person, date, unit, original row location, and source version.",
)


def run_lens_diagnostics(client: ZetarisClient, tables: LensTables) -> dict[str, Any]:
    """Prove the registered sources can be queried; never decide a review finding."""
    queries = (
        ("staff_time", cross_source_sql(tables.timesheets, tables.report_a, tables.report_b),
         ("source_id", "recorded_hours", "allocated_hours", "claim_count")),
        ("expenses", cross_expense_sql(tables.receipts, tables.report_a, tables.report_b),
         ("source_id", "recorded_usd", "allocated_usd", "claim_count")),
        ("activities", activity_count_sql(tables.activity), ("activity_records",)),
    )
    rows: dict[str, list[dict[str, Any]]] = {}
    request_ids: dict[str, str] = {}
    for label, sql, fields in queries:
        result = client.query(sql)
        request_ids[label] = result.request_id
        if result.status != "ok":
            return {"status": result.status, "message": result.message, "request_ids": request_ids,
                    "review_eligible": False, "limitations": LIMITATIONS}
        try:
            rows[label] = _as_records(result, fields)
        except ValueError as exc:
            return {"status": "error", "message": str(exc), "request_ids": request_ids,
                    "review_eligible": False, "limitations": LIMITATIONS}
    return {"status": "ok", "rows": rows, "request_ids": request_ids,
            "review_eligible": False, "limitations": LIMITATIONS}


def read_lens_evidence(_client: ZetarisClient, _tables: LensTables) -> dict[str, Any]:
    """Fail closed if an app tries to use diagnostic aggregates as review evidence."""
    raise RuntimeError(
        "Zetaris aggregate diagnostics are not review evidence: unmatched claims, "
        "reporting period, row provenance, and source versions must be resolved first."
    )
