#!/usr/bin/env python3
"""T03 — Functional Score. Threshold ≥0.95."""
import argparse
import json
import sys
from pathlib import Path
import yaml


def load_md(md_path: Path):
    content = md_path.read_text()
    parts = content.split("---", 2)
    return yaml.safe_load(parts[1]) or {}


def norm(x):
    if x is None:
        return None
    return str(x).strip().upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.cfg).read_text())
    md = load_md(Path(args.md))

    # Option A fix (schema vs validator alignment, 2026-04-23 human sign-off):
    # Filter CFG data_items to 01-level only to match COBOL-MD-SCHEMA.md §Data Layer,
    # which restricts MD data_items[] to level-01 working-storage items.
    # Sub-level items (05/10/15), FD record descriptors, and 88-level condition names
    # belong in a future v1.1 sub_items[] structure, not in the primary data_items[] array.
    cfg_items_all = cfg.get("data_items", [])
    cfg_items_01 = [d for d in cfg_items_all if d.get("level") == 1]
    cfg_items = {d["name"].upper(): d for d in cfg_items_01}
    md_items = {d.get("name", "").upper(): d for d in md.get("data_items", []) if d.get("name")}

    checks = []
    for name, cd in cfg_items.items():
        md_d = md_items.get(name)
        if md_d is None:
            checks.append({"name": name, "field": "presence", "pass": False, "reason": "missing in MD"})
            continue
        for field in ("level", "picture", "usage"):
            cfg_v = norm(cd.get(field))
            md_v = norm(md_d.get(field))
            if cfg_v != md_v:
                checks.append({"name": name, "field": field, "pass": False, "reason": f"cfg={cfg_v!r} md={md_v!r}"})
            else:
                checks.append({"name": name, "field": field, "pass": True})
        # dead_code_flag cross-check
        cfg_reachable = cd.get("reachable", True)
        md_dead = md_d.get("dead_code_flag", False)
        if bool(md_dead) == bool(not cfg_reachable):
            checks.append({"name": name, "field": "dead_code_flag", "pass": True})
        else:
            checks.append({"name": name, "field": "dead_code_flag", "pass": False,
                           "reason": f"cfg reachable={cfg_reachable} md dead={md_dead}"})

    matched = sum(1 for c in checks if c["pass"])
    total = len(checks)
    score = (matched / total) if total else 1.0

    # AIFIRST-PLAN-3PASS.md §11 — CICS subtype threshold override.
    # CICS-Online programs carry CFG edges (EXEC CICS HANDLE CONDITION, XCTL,
    # RETURN, LINK) that Cobol-REKT represents with MEDIUM confidence because
    # the exact CICS runtime semantics are beyond static analysis. When a
    # program is declared subtype=CICS-Online AND its Phase-0 cfg_confidence is
    # MEDIUM, the T03 gate relaxes from ≥0.95 to ≥0.80 so the MEDIUM-confidence
    # edges do not block an otherwise-valid translation.
    subtype = norm(md.get("subtype") or md.get("program_subtype"))
    cfg_confidence = norm(cfg.get("cfg_confidence") or cfg.get("confidence"))
    cics_override_active = (subtype == "CICS-ONLINE" and cfg_confidence == "MEDIUM")
    threshold = 0.80 if cics_override_active else 0.95
    override_note = (
        "CICS-Online + MEDIUM cfg_confidence → threshold relaxed to 0.80 per plan §11"
        if cics_override_active else None
    )

    out = {
        "tier": "T03",
        "file": str(args.md),
        "score": round(score, 4),
        "matched": matched,
        "total": total,
        "threshold": threshold,
        "threshold_default": 0.95,
        "threshold_override_active": cics_override_active,
        "threshold_override_reason": override_note,
        "subtype": subtype,
        "cfg_confidence": cfg_confidence,
        "pass": score >= threshold,
        "failures": [c for c in checks if not c["pass"]][:40],
        "cfg_items_total": len(cfg_items_all),
        "cfg_items_01": len(cfg_items_01),
        "validator_version": "v1.0.2-cics-threshold",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({"tier": "T03", "file": args.md, "score": out["score"], "pass": out["pass"]}))
    sys.exit(0 if out["pass"] else 1)


if __name__ == "__main__":
    main()
