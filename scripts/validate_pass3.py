#!/usr/bin/env python3
"""
validate_pass3.py — T-PASS3 deterministic validator.

Tiers (plan §7):
  T-PASS3-COVERAGE   — every Pass 2 seq appears in exactly one
                       logical_groups[].statements[] list (blocking).
  T-PASS3-D          — every business_rule.derived_from references an
                       existing LG id in the same paragraph (blocking).
  T-PASS3-P          — semantic_pattern is one of the 9 defined enum
                       values (non-blocking flag; `unknown` is valid but
                       triggers human review).
  T-PASS3-CONFIDENCE — any business_rule.confidence < 0.70 is flagged
                       (non-blocking).

Input: the v1.1 Markdown file (YAML front-matter + procedure_paragraphs[]
with logical_groups[] and business_rules[]) and the Pass 2 propositions JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml  # PyYAML 6.x
except ImportError:  # pragma: no cover
    print("PyYAML required", file=sys.stderr)
    sys.exit(1)

SEMANTIC_PATTERNS = {
    "guard-with-override", "accumulation", "state-machine", "delegation",
    "sequential", "conditional-branch", "cics-interaction", "file-io", "unknown",
}


def load_md(path: Path) -> dict:
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Front matter missing in {path}")
    return yaml.safe_load(parts[1])


def main() -> int:
    ap = argparse.ArgumentParser(description="T-PASS3 validator")
    ap.add_argument("--md", type=Path, required=True)
    ap.add_argument("--propositions", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    md = load_md(args.md)
    props = json.loads(args.propositions.read_text())

    prop_by_para: dict[str, set[int]] = {}
    for p in props:
        prop_by_para.setdefault(p["paragraph"], set()).add(p["seq"])

    coverage_errors: list[str] = []
    derivation_errors: list[str] = []
    pattern_errors: list[str] = []
    confidence_flags: list[str] = []

    for para in md.get("procedure_paragraphs", []):
        name = para.get("name", "")
        lgs = para.get("logical_groups") or []
        brs = para.get("business_rules") or []
        pattern = para.get("semantic_pattern")

        # Coverage
        expected = prop_by_para.get(name, set())
        covered: set[int] = set()
        doubled: set[int] = set()
        for lg in lgs:
            for s in lg.get("statements", []) or []:
                if s in covered:
                    doubled.add(s)
                covered.add(s)
        if expected and covered != expected:
            missing = sorted(expected - covered)
            extra = sorted(covered - expected)
            if missing:
                coverage_errors.append(f"{name}: missing seqs {missing[:10]}")
            if extra:
                coverage_errors.append(f"{name}: extra seqs {extra[:10]}")
        if doubled:
            coverage_errors.append(f"{name}: doubled seqs {sorted(doubled)[:10]}")

        # Derivation
        lg_ids = {lg.get("id") for lg in lgs if lg.get("id")}
        for br in brs:
            dfrm = br.get("derived_from") or []
            for did in dfrm:
                if did not in lg_ids:
                    derivation_errors.append(f"{name}: business_rule {br.get('id')} derived_from unknown LG '{did}'")

        # Pattern
        if pattern is not None and pattern not in SEMANTIC_PATTERNS:
            pattern_errors.append(f"{name}: invalid semantic_pattern '{pattern}'")

        # Confidence flags
        for br in brs:
            c = br.get("confidence")
            if isinstance(c, (int, float)) and c < 0.70:
                confidence_flags.append(f"{name}: business_rule {br.get('id')} confidence {c}")

    out = {
        "tier": "T-PASS3",
        "file": str(args.md),
        "coverage": {
            "tier": "T-PASS3-COVERAGE",
            "pass": len(coverage_errors) == 0,
            "blocking": True,
            "errors": coverage_errors[:30],
        },
        "derivation": {
            "tier": "T-PASS3-D",
            "pass": len(derivation_errors) == 0,
            "blocking": True,
            "errors": derivation_errors[:30],
        },
        "pattern": {
            "tier": "T-PASS3-P",
            "pass": len(pattern_errors) == 0,
            "blocking": False,
            "errors": pattern_errors[:30],
        },
        "confidence": {
            "tier": "T-PASS3-CONFIDENCE",
            "pass": len(confidence_flags) == 0,
            "blocking": False,
            "flags": confidence_flags[:30],
        },
        "pass": len(coverage_errors) == 0 and len(derivation_errors) == 0,
        "validator_version": "v1.0.0",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("tier", "file", "pass")}))
    return 0 if out["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
