"""Mechanical conformance check for a momotron plan bundle.

Usage: python conformance.py <bundle>. Writes a review pass to <bundle>/reviews/ and the
result JSON to $MOMOTRON_RESULT. Never edits the definition.
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path

import yaml

ABS = re.compile(r"(^|\s)(/Users/|/home/|[A-Za-z]:\\)")


def concerns_for(bundle: Path) -> list[dict]:
    plan = yaml.safe_load((bundle / "plan.yaml").read_text())
    out = []

    def add(cid, sev, msg):
        out.append({"id": cid, "severity": sev, "evidence": msg})

    if not str(plan.get("objective", "")).strip():
        add("C-objective", "high", "plan.yaml: objective is empty")
    steps = plan.get("steps") or []
    if not steps:
        add("C-steps", "high", "plan.yaml: no steps")
    for s in steps:
        if s.get("type") == "task":
            if not s.get("checks"):
                add(f"C-checks-{s['id']}", "medium", f"steps.{s['id']}: no acceptance checks; success rests on worker claims")
            if not (s.get("description") or s.get("description_asset")):
                add(f"C-desc-{s['id']}", "medium", f"steps.{s['id']}: no description")
    ids = {s.get("id") for s in steps}
    covered = set()
    for c in plan.get("criteria") or []:
        covered |= set(c.get("verified_by") or [])
        if not c.get("verified_by"):
            add(f"C-criterion-{c['id']}", "medium", f"criteria.{c['id']}: not traced to any step")
    if plan.get("criteria") and not covered & ids:
        add("C-trace", "high", "no criterion is verified by an existing step")
    text = (bundle / "plan.yaml").read_text()
    if ABS.search(text):
        add("C-machine-path", "high", "plan.yaml embeds an absolute machine path; use bindings")
    if not any((bundle / "references").glob("*")):
        add("C-references", "low", "references/ is empty; capture the originating request")
    return out


def main() -> int:
    bundle = Path(sys.argv[1]).resolve()
    concerns = concerns_for(bundle)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")
    rel = f"reviews/conformance-{stamp}.md"
    rows = "\n".join(f"| {c['id']} | {c['severity']} | {c['evidence']} |" for c in concerns) or "| — | — | no concerns |"
    verdict = "revise" if any(c["severity"] == "high" for c in concerns) else "pass"
    (bundle / rel).write_text(
        "---\ntype: Review\nokf_spec: MOMOTRON-PLAN\ndescription: Mechanical conformance pass.\n---\n"
        f"# Conformance pass\n\nVerdict: **{verdict}**\n\n| Concern | Severity | Evidence |\n| :-- | :-- | :-- |\n{rows}\n")
    result = {"status": "succeeded", "summary": f"{len(concerns)} concern(s); verdict {verdict}",
              "outputs": {"route": verdict, "concerns": concerns, "review": rel}, "artifacts": [rel]}
    Path(os.environ["MOMOTRON_RESULT"]).write_text(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
