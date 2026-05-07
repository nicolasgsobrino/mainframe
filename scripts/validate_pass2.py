#!/usr/bin/env python3
"""
validate_pass2.py — T-PASS2 validator.

Tiers (plan §5):
  T-PASS2-COVERAGE — every seq in Pass 1 has exactly one proposition.
  T-PASS2-OPS      — for LLM-generated propositions, every field name in
                     the text is present in data_items_inventory; unresolved
                     → flag (non-blocking) and excluded from Pass 3 LLM input.
  T-PASS2-OVR      — overrides_seq relationships reference real predecessor
                     seqs with the same `modifies` field (non-blocking flag).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="T-PASS2 validator")
    ap.add_argument("--annotations", type=Path, required=True)
    ap.add_argument("--propositions", type=Path, required=True)
    ap.add_argument("--cfg", type=Path, required=True, help="Phase-0 CFG JSON (for data_items inventory)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    anns = json.loads(args.annotations.read_text())
    props = json.loads(args.propositions.read_text())
    cfg = json.loads(args.cfg.read_text())

    inventory = {d["name"].upper() for d in cfg.get("data_items", []) if d.get("name")}

    ann_seqs = {a["seq"] for a in anns}
    prop_seqs = {p["seq"] for p in props}

    missing_in_props = sorted(ann_seqs - prop_seqs)
    extra_in_props = sorted(prop_seqs - ann_seqs)
    coverage_pass = (not missing_in_props and not extra_in_props)

    # OPS: for LLM-sourced propositions, check referenced field names.
    ops_errors: list[str] = []
    for p in props:
        if p["proposition_source"] != "LLM":
            continue
        if not p.get("proposition"):
            continue
        for tok in re.findall(r"[A-Z][A-Z0-9\-]{2,}", p["proposition"]):
            # Skip common English words that happen to look like identifiers.
            if tok in {"WHEN", "AFTER", "BEFORE", "WHILE", "WITH", "FROM", "INTO",
                       "FOR", "NOT", "AND", "OR", "IF", "THEN", "ELSE",
                       "COBOL", "CICS", "SQL"}:
                continue
            if tok not in inventory:
                ops_errors.append(f"seq {p['seq']}: token {tok} not in data_items inventory")
                break

    # OVR: every overrides_seq must reference an earlier seq in same paragraph,
    # and both must share the same `modifies` field.
    seq_index = {p["seq"]: p for p in props}
    ovr_errors: list[str] = []
    overrides_count = 0
    for p in props:
        if "overrides_seq" not in p:
            continue
        overrides_count += 1
        ref = seq_index.get(p["overrides_seq"])
        if ref is None:
            ovr_errors.append(f"seq {p['seq']}: overrides_seq {p['overrides_seq']} not found")
            continue
        if ref["paragraph"] != p["paragraph"]:
            ovr_errors.append(f"seq {p['seq']}: override crosses paragraph boundary")
        if ref.get("modifies") != p.get("modifies"):
            ovr_errors.append(f"seq {p['seq']}: override modifies mismatch ({ref.get('modifies')} vs {p.get('modifies')})")
        if p["overrides_seq"] >= p["seq"]:
            ovr_errors.append(f"seq {p['seq']}: override points forward or to self")

    out = {
        "tier": "T-PASS2",
        "file": str(args.propositions),
        "coverage": {
            "tier": "T-PASS2-COVERAGE",
            "pass": coverage_pass,
            "blocking": True,
            "missing_in_propositions": missing_in_props[:20],
            "extra_in_propositions": extra_in_props[:20],
        },
        "ops": {
            "tier": "T-PASS2-OPS",
            "pass": len(ops_errors) == 0,
            "blocking": False,
            "errors": ops_errors[:20],
        },
        "ovr": {
            "tier": "T-PASS2-OVR",
            "pass": len(ovr_errors) == 0,
            "blocking": False,
            "overrides_count": overrides_count,
            "errors": ovr_errors[:20],
        },
        "pass": coverage_pass,
        "validator_version": "v1.0.0",
        "stats": {
            "total": len(props),
            "template": sum(1 for p in props if p["proposition_source"] == "TEMPLATE"),
            "partial": sum(1 for p in props if p["proposition_source"] == "PARTIAL"),
            "llm": sum(1 for p in props if p["proposition_source"] == "LLM"),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("tier", "file", "pass", "stats")}))
    return 0 if out["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
