#!/usr/bin/env python3
"""T02-R — REDEFINES Completeness. Absolute, no threshold."""
import argparse
import json
import sys
from pathlib import Path
import yaml


def load_md(md_path: Path):
    content = md_path.read_text()
    parts = content.split("---", 2)
    return yaml.safe_load(parts[1]) or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.cfg).read_text())
    md = load_md(Path(args.md))

    errors = []
    cfg_redef_names = {r["name"].upper() for r in cfg.get("redefines_clauses", [])}

    # Option A fix (schema vs validator alignment, 2026-04-23 human sign-off):
    # A REDEFINES condition legitimately references sub-fields (05/10-level), which the
    # MD schema keeps out of data_items[] (01-only per COBOL-MD-SCHEMA.md §Data Layer).
    # Resolve the ambiguity by expanding the allowed referent set: condition strings may
    # reference any field the CFG knows about (all levels) OR any 88-level condition
    # name, not only the 01-level items in MD.data_items[].
    md_field_names = {d.get("name", "").upper() for d in md.get("data_items", []) if d.get("name")}
    cfg_all_field_names = {d.get("name", "").upper() for d in cfg.get("data_items", []) if d.get("name")}
    allowed_referents = md_field_names | cfg_all_field_names

    md_items_by_name = {d.get("name", "").upper(): d for d in md.get("data_items", [])}

    # 1) every cfg redefines item must appear in md with non-null redefines
    for nm in cfg_redef_names:
        if nm not in md_items_by_name:
            errors.append(f"REDEFINES item {nm} missing from data_items[]")
            continue
        item = md_items_by_name[nm]
        if not item.get("redefines"):
            errors.append(f"Item {nm} has redefines=null in MD but CFG has REDEFINES clause")

    # 2) any md item with redefines != null must have redefines_interpretations[] with ≥2 entries
    for item in md.get("data_items", []):
        nm = item.get("name", "").upper()
        if item.get("redefines"):
            interps = item.get("redefines_interpretations") or []
            if len(interps) < 2:
                errors.append(f"Item {nm}: redefines_interpretations[] has {len(interps)} entries (need ≥2)")
            for i, entry in enumerate(interps):
                for field in ("condition", "interpreted_as", "encoding"):
                    if not entry.get(field):
                        errors.append(f"Item {nm} interpretation[{i}]: missing {field}")
                cond = (entry.get("condition") or "").upper()
                # condition must reference a field the CFG recognises at any level
                # (see Option A fix note above).
                if cond and not any(fld in cond for fld in allowed_referents if fld):
                    errors.append(f"Item {nm} interpretation[{i}]: condition does not reference any CFG-known field")

    out = {
        "tier": "T02-R",
        "file": str(args.md),
        "pass": len(errors) == 0,
        "errors": errors,
        "cfg_redefines_count": len(cfg_redef_names),
        "validator_version": "v1.0.1-option-a",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out))
    sys.exit(0 if out["pass"] else 1)


if __name__ == "__main__":
    main()
