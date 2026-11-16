"""Portability validation: the bundle must be readable and executable when copied elsewhere.

Usage: python portability.py <bundle>. Fails (status "failed") on any blocking problem.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import yaml


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def problems_for(bundle: Path) -> list[str]:
    out = []
    for member in ("index.md", "log.md", "plan.yaml", "context.md"):
        if not (bundle / member).is_file():
            out.append(f"missing {member}")
    closure_path = bundle / "processes" / "closure.yaml"
    if not closure_path.is_file():
        return out + ["not frozen: processes/closure.yaml missing"]
    closure = yaml.safe_load(closure_path.read_text())
    for pid, entry in (closure.get("processes") or {}).items():
        for rel, digest in entry["files"].items():
            f = bundle / "processes" / pid / rel
            if not f.is_file() or sha(f) != digest:
                out.append(f"processes/{pid}/{rel} differs from closure")
    for f in bundle.rglob("*"):
        if f.is_symlink():
            target = f.resolve()
            if bundle != target and bundle not in target.parents:
                out.append(f"{f.relative_to(bundle)} links outside the bundle")
    home = str(Path.home())
    for f in [bundle / "plan.yaml", *sorted((bundle / "plan-assets").rglob("*"))]:
        if f.is_file() and home in f.read_text(errors="ignore"):
            out.append(f"{f.relative_to(bundle)} embeds a home-directory path")
    index = (bundle / "index.md").read_text() if (bundle / "index.md").is_file() else ""
    for line in index.splitlines():
        if line.startswith("| [`"):
            name = line.split("`")[1].rstrip("/")
            if not (bundle / name).exists():
                out.append(f"index.md lists missing member {name}")
    return out


def main() -> int:
    bundle = Path(sys.argv[1]).resolve()
    problems = problems_for(bundle)
    result = {"status": "failed" if problems else "succeeded",
              "summary": "; ".join(problems) or "bundle is portable",
              "outputs": {"problems": problems}, "artifacts": []}
    Path(os.environ["MOMOTRON_RESULT"]).write_text(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
