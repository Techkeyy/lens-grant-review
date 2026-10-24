"""Live Zetaris connection and aggregate diagnostic. Run: python -m zetaris.smoke"""

import os
import re
import sys

from .client import ZetarisClient, ZetarisConfig


_TABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


def _table(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not _TABLE.fullmatch(value):
        raise ValueError(f"{name} must be set to a registered database.table name")
    return value


def cross_source_sql(timesheets: str, report_a: str, report_b: str) -> str:
    """Diagnostic inner join; unmatched claims are deliberately not represented."""
    for name in (timesheets, report_a, report_b):
        if not _TABLE.fullmatch(name):
            raise ValueError("Table names must be registered database.table identifiers")
    return f"""SELECT t.source_id, t.hours AS recorded_hours,
       SUM(c.quantity) AS allocated_hours, COUNT(*) AS claim_count
FROM {timesheets} t
JOIN (
  SELECT source_id, quantity FROM {report_a} WHERE kind = 'staff_time'
  UNION ALL
  SELECT source_id, quantity FROM {report_b} WHERE kind = 'staff_time'
) c ON t.source_id = c.source_id
GROUP BY t.source_id, t.hours
ORDER BY t.source_id"""


def cross_expense_sql(receipts: str, report_a: str, report_b: str) -> str:
    """Compare receipt amounts with expense claims from both grant drafts."""
    for name in (receipts, report_a, report_b):
        if not _TABLE.fullmatch(name):
            raise ValueError("Table names must be registered database.table identifiers")
    return f"""SELECT r.source_id, r.amount_usd AS recorded_usd,
       SUM(c.quantity) AS allocated_usd, COUNT(*) AS claim_count
FROM {receipts} r
JOIN (
  SELECT source_id, quantity FROM {report_a} WHERE kind = 'expense'
  UNION ALL
  SELECT source_id, quantity FROM {report_b} WHERE kind = 'expense'
) c ON r.source_id = c.source_id
GROUP BY r.source_id, r.amount_usd
ORDER BY r.source_id"""


def activity_count_sql(activity: str) -> str:
    if not _TABLE.fullmatch(activity):
        raise ValueError("Table name must be a registered database.table identifier")
    return f"SELECT COUNT(*) AS activity_records FROM {activity}"


def _cell(row: dict | tuple, key: str, index: int):
    """Official REST helpers return positional data arrays; UI may add headers."""
    return row.get(key) if isinstance(row, dict) else row[index]


def main() -> int:
    print("DIAGNOSTIC ONLY: aggregates omit unmatched claims and row provenance; do not use as Lens review findings.")
    try:
        config = ZetarisConfig.from_environment()
    except ValueError as exc:
        print(f"Zetaris configuration error: {exc}", file=sys.stderr)
        return 2
    client = ZetarisClient(config)
    smoke = client.query("SELECT 1 AS one")
    print(f"connection: {smoke.status}; {smoke.message}; request_id={smoke.request_id or 'none'}")
    if smoke.status != "ok" or not smoke.rows or str(_cell(smoke.rows[0], "one", 0)) != "1":
        return 1
    databases = client.query("SHOW LIGHTNING DATABASES")
    print(f"databases: {databases.status}; {databases.message}; request_id={databases.request_id or 'none'}")
    if databases.status != "ok":
        return 1
    try:
        report_a, report_b = _table("ZETARIS_REPORT_A_TABLE"), _table("ZETARIS_REPORT_B_TABLE")
        sql = cross_source_sql(_table("ZETARIS_TIMESHEETS_TABLE"), report_a, report_b)
        expense_sql = cross_expense_sql(_table("ZETARIS_RECEIPTS_TABLE"), report_a, report_b)
        activity_sql = activity_count_sql(_table("ZETARIS_ACTIVITY_TABLE"))
    except ValueError as exc:
        print(f"cross-source configuration error: {exc}", file=sys.stderr)
        return 2
    result = client.query(sql)
    print(f"cross-source: {result.status}; {result.message}; request_id={result.request_id or 'none'}")
    if result.status != "ok" or not result.rows:
        return 1
    for row in result.rows:
        print(f"source_id={_cell(row, 'source_id', 0)}; recorded_hours={_cell(row, 'recorded_hours', 1)}; allocated_hours={_cell(row, 'allocated_hours', 2)}; claim_count={_cell(row, 'claim_count', 3)}")
    expense = client.query(expense_sql)
    print(f"expense: {expense.status}; {expense.message}; request_id={expense.request_id or 'none'}")
    if expense.status != "ok" or not expense.rows:
        return 1
    for row in expense.rows:
        print(f"source_id={_cell(row, 'source_id', 0)}; recorded_usd={_cell(row, 'recorded_usd', 1)}; allocated_usd={_cell(row, 'allocated_usd', 2)}; claim_count={_cell(row, 'claim_count', 3)}")
    activity = client.query(activity_sql)
    print(f"activity: {activity.status}; {activity.message}; request_id={activity.request_id or 'none'}")
    if activity.status != "ok" or not activity.rows:
        return 1
    print(f"activity_records={_cell(activity.rows[0], 'activity_records', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
