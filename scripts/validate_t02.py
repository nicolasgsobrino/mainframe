#!/usr/bin/env python3
"""T02 — Structural Completeness (CFG diff). Threshold 100% (absolute).

Verifies every paragraph / section / 01-level data item / copybook in the
CFG JSON is present in the translated MD.
"""
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

    # Paragraphs
    cfg_paragraphs = {p["name"].upper() for p in cfg.get("paragraphs", [])}
    md_paragraphs = {p.get("name", "").upper() for p in md.get("procedure_paragraphs", []) if p.get("name")}
    missing = cfg_paragraphs - md_paragraphs
    if missing:
        errors.append(f"Missing paragraphs in MD: {sorted(missing)}")

    # 01-level data items
    cfg_01 = {d["name"].upper() for d in cfg.get("data_items", []) if d.get("level") == 1}
    md_items = {d.get("name", "").upper() for d in md.get("data_items", []) if d.get("name")}
    missing_items = cfg_01 - md_items
    if missing_items:
        errors.append(f"Missing 01-level data items in MD: {sorted(missing_items)}")

    # Copybooks
    cfg_cp = {c.upper() for c in cfg.get("copybooks_used", [])}
    md_cp = {c.get("name", "").upper() for c in md.get("copybooks_used", []) if isinstance(c, dict)}
    missing_cp = cfg_cp - md_cp
    if missing_cp:
        errors.append(f"Missing copybooks in MD: {sorted(missing_cp)}")

    # Calls
    cfg_calls = {c.upper() for c in cfg.get("calls_to", [])}
    md_calls = {c.get("program", "").upper() for c in md.get("calls_to", []) if isinstance(c, dict)}
    missing_calls = cfg_calls - md_calls
    if missing_calls:
        errors.append(f"Missing calls_to entries in MD: {sorted(missing_calls)}")

    out = {
        "tier": "T02",
        "file": str(args.md),
        "pass": len(errors) == 0,
        "errors": errors,
        "counts": {
            "paragraphs_cfg": len(cfg_paragraphs),
            "paragraphs_md": len(md_paragraphs),
            "data_items_01_cfg": len(cfg_01),
            "data_items_md": len(md_items),
        },
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out))
    sys.exit(0 if out["pass"] else 1)


if __name__ == "__main__":
    main()
