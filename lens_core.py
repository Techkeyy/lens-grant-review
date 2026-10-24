"""Narrow deterministic reconciliation core for Lens.

All data in examples/ is synthetic. This module makes no model or sponsor calls.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _amount(value: object) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid quantity: {value!r}") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"Quantity must be finite and nonnegative: {value!r}")
    return amount


def _location(item: dict) -> dict:
    ref = item.get("ref")
    if not isinstance(ref, dict) or not ref.get("file") or not ref.get("row"):
        raise ValueError(f"Record {item.get('id')!r} lacks file/row provenance")
    location = {"id": item["id"], "file": ref["file"], "row": ref["row"]}
    if "zetaris" in ref:
        location["zetaris"] = ref["zetaris"]
    return location


def _date(value: object) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ISO date: {value!r}") from exc


def _finding(code: str, status: str, message: str, claims: list[dict], sources: list[dict], arithmetic: dict | None = None) -> dict:
    return {
        "code": code,
        "status": status,
        "message": message,
        "claims": [_location(item) for item in claims],
        "sources": [_location(item) for item in sources],
        "arithmetic": arithmetic,
    }


def analyze_case(case: dict) -> dict:
    """Reconcile explicit source IDs, returning evidence-backed questions and clears.

    An absent or ambiguous identity is never silently fuzzy-matched. The caller
    must present candidate source records for human review instead.
    """
    sources = case.get("sources", [])
    claims = case.get("claims", [])
    if not isinstance(sources, list) or not isinstance(claims, list):
        raise ValueError("sources and claims must be lists")
    source_by_id = {item["id"]: item for item in sources}
    claim_ids = [item["id"] for item in claims]
    if len(source_by_id) != len(sources) or len(set(claim_ids)) != len(claims):
        raise ValueError("Source and claim IDs must be unique")
    for item in sources + claims:
        _location(item)

    period = case.get("reporting_period")
    if not isinstance(period, dict) or not period.get("start") or not period.get("end"):
        raise ValueError("A reporting_period with start and end is required")
    period_start, period_end = _date(period["start"]), _date(period["end"])
    if period_start > period_end:
        raise ValueError("Reporting period starts after it ends")

    def in_period(source: dict) -> bool:
        return period_start <= _date(source.get("date")) <= period_end

    findings: list[dict] = []
    groups: dict[str, list[dict]] = defaultdict(list)
    project_questions: set[str] = set()

    for claim in claims:
        if claim.get("kind") == "activity_count":
            evidence_ids = claim.get("evidence_ids", [])
            if not isinstance(evidence_ids, list):
                raise ValueError("Activity evidence_ids must be a list")
            missing_ids = [key for key in evidence_ids if key not in source_by_id]
            wrong_kind = [source_by_id[key] for key in evidence_ids if key in source_by_id and source_by_id[key].get("kind") != "activity"]
            out_of_period = [source_by_id[key] for key in evidence_ids if key in source_by_id and source_by_id[key].get("kind") == "activity" and not in_period(source_by_id[key])]
            evidence = [source_by_id[key] for key in evidence_ids if key in source_by_id and source_by_id[key].get("kind") == "activity" and in_period(source_by_id[key])]
            stated = _amount(claim["quantity"])
            verified = len({item["id"] for item in evidence})
            if missing_ids or wrong_kind or out_of_period:
                findings.append(_finding(
                    "ACTIVITY_LINKS_UNVERIFIED", "needs_review",
                    "Some linked activity IDs are missing, have the wrong type, or fall outside the reporting period.",
                    [claim], wrong_kind + out_of_period,
                    {"missing_ids": missing_ids, "wrong_kind_ids": [item["id"] for item in wrong_kind], "outside_period_ids": [item["id"] for item in out_of_period]},
                ))
            if stated > verified:
                findings.append(_finding(
                    "ACTIVITY_SUPPORT_GAP", "needs_evidence",
                    f"Report states {stated} sessions; {verified} distinct activity records are linked.",
                    [claim], evidence,
                    {"reported": str(stated), "linked_distinct_records": verified, "gap": str(stated - verified), "unit": "sessions"},
                ))
            continue
        if claim.get("kind") != "allocation":
            raise ValueError(f"Unsupported claim kind: {claim.get('kind')!r}")
        source_id = claim.get("source_id")
        if not source_id or source_id not in source_by_id:
            candidates = [source_by_id[key] for key in claim.get("candidate_source_ids", []) if key in source_by_id]
            findings.append(_finding(
                "SOURCE_IDENTITY_UNCERTAIN", "needs_review",
                "This claim has no confirmed source record. Review possible matches before reconciliation.",
                [claim], candidates,
            ))
            continue
        source = source_by_id[source_id]
        if source.get("kind") not in ("staff_time", "expense") or claim.get("unit") != source.get("unit"):
            findings.append(_finding(
                "SOURCE_MISMATCH", "needs_review",
                "Claim and source type or unit do not agree.",
                [claim], [source],
            ))
            continue
        if not in_period(source):
            findings.append(_finding(
                "SOURCE_OUTSIDE_PERIOD", "needs_review",
                "The source record falls outside this report's period.",
                [claim], [source],
            ))
            continue
        if source["kind"] == "staff_time" and (not claim.get("person") or claim["person"] != source.get("person")):
            findings.append(_finding(
                "STAFF_IDENTITY_UNVERIFIED", "needs_review",
                "The claimed staff member is missing or differs from the source timesheet.",
                [claim], [source],
            ))
            continue
        if source["kind"] == "expense" and (not claim.get("vendor") or claim["vendor"] != source.get("vendor")):
            findings.append(_finding(
                "EXPENSE_IDENTITY_UNVERIFIED", "needs_review",
                "The claimed vendor is missing or differs from the source expense.",
                [claim], [source],
            ))
            continue
        if source["kind"] == "staff_time" and source.get("project_grant") and source["project_grant"].strip().casefold() != str(claim.get("grant", "")).strip().casefold():
            findings.append(_finding(
                "TIMESHEET_PROJECT_DIFFERS", "needs_review",
                f"Timesheet names {source['project_grant']!r}; this report charges the time to {claim.get('grant')!r}. Confirm the cross-program allocation basis.",
                [claim], [source],
            ))
            project_questions.add(source_id)
        _amount(claim["quantity"])
        groups[source_id].append(claim)

    for source_id, linked in groups.items():
        source = source_by_id[source_id]
        total = sum((_amount(item["quantity"]) for item in linked), Decimal("0"))
        recorded = _amount(source["quantity"])
        arithmetic = {"allocated_total": str(total), "source_total": str(recorded), "unit": source["unit"]}
        if total > recorded:
            findings.append(_finding(
                "OVERALLOCATED_SOURCE", "needs_correction",
                f"Claims allocate {total} {source['unit']} from a source recording only {recorded}.",
                linked, [source], arithmetic,
            ))
        elif source_id in project_questions:
            findings.append(_finding(
                "ALLOCATION_TOTAL_WITH_PROJECT_QUESTION", "needs_review",
                f"Linked allocations total {total} of {recorded} {source['unit']} recorded, but a timesheet project label differs from a report grant.",
                linked, [source], arithmetic,
            ))
        else:
            findings.append(_finding(
                "ALLOCATION_WITHIN_SOURCE", "clear",
                f"Linked allocations total {total} of {recorded} {source['unit']} recorded.",
                linked, [source], arithmetic,
            ))

    order = {"needs_correction": 0, "needs_evidence": 1, "needs_review": 2, "clear": 3}
    findings.sort(key=lambda item: (order[item["status"]], item["code"], item["claims"][0]["id"]))
    return {"data_label": case.get("label", "unlabelled"), "findings": findings}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Reconcile a Lens case JSON file")
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    case = json.loads(args.case.read_text(encoding="utf-8"))
    print(json.dumps(analyze_case(case), indent=2))


if __name__ == "__main__":
    main()
