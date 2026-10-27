"""Regenerate three documented synthetic input/output runs from lens_core."""

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lens_core import analyze_case  # noqa: E402


base = json.loads((ROOT / "examples" / "synthetic_case.json").read_text(encoding="utf-8"))
split = copy.deepcopy(base)
for claim in split["claims"]:
    if claim["id"] in ("A-TIME-1", "B-TIME-1"):
        claim["quantity"] = "2"
activity = copy.deepcopy(base)
next(claim for claim in activity["claims"] if claim["id"] == "A-ACT-1")["quantity"] = "8"

runs = []
for name, description, case in (
    ("original", "Two reports each claim all four hours; ten sessions are reported with eight records.", base),
    ("corrected_split", "The two reports each claim two of the four recorded hours.", split),
    ("revised_activity_claim", "The draft now reports eight sessions against eight linked activity records.", activity),
):
    findings = analyze_case(case)["findings"]
    runs.append({"scenario": name, "description": description, "input": case,
                 "output": [{"code": item["code"], "status": item["status"],
                             "arithmetic": item.get("arithmetic"),
                             "claim_ids": [ref["id"] for ref in item["claims"]],
                             "source_ids": [ref["id"] for ref in item["sources"]]}
                            for item in findings]})

out = ROOT / "examples" / "sample_runs.json"
out.write_bytes((json.dumps(runs, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(out)
