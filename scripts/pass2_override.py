#!/usr/bin/env python3
"""
pass2_override.py — overrides_seq post-processing (DETERMINISTIC).

Plan: AIFIRST-PLAN-3PASS.md §4 "Identifying overrides_seq"

Rule (literal): for two statements A and B in the same paragraph that modify
the same field, where B is in a branch context that did not exist at A's
seq — set B.overrides_seq = A.seq.

Since the Pass 1 annotator assigns a textual `cfg_branch_context` to branch
verbs (IF/EVALUATE) and propagates it to following statements until the next
branch point, we can detect overrides by:
  - same `modifies` field
  - same `paragraph`
  - B has a non-null `cfg_branch_context` that differs from A's

We emit a validator-friendly record: the LATER statement gets
`overrides_seq = <earlier seq>`. If more than one earlier candidate exists,
we record the immediate predecessor (largest seq < B.seq).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def detect_overrides(propositions: list[dict]) -> list[dict]:
    # Group by (paragraph, modifies). Ignore propositions whose `modifies`
    # is None — they cannot participate in override relationships.
    by_key: dict[tuple[str, str], list[dict]] = {}
    for p in propositions:
        mod = p.get("modifies")
        if not mod:
            continue
        by_key.setdefault((p["paragraph"], mod), []).append(p)

    # Within each group, if cfg_branch_context changes between an earlier and
    # a later statement, the later one overrides the earlier one.
    for key, records in by_key.items():
        records.sort(key=lambda r: r["seq"])
        for i, later in enumerate(records):
            if i == 0:
                continue
            earlier_candidates = [r for r in records[:i]
                                  if (r.get("cfg_branch_context") or "") != (later.get("cfg_branch_context") or "")]
            if not earlier_candidates:
                continue
            predecessor = earlier_candidates[-1]
            later["overrides_seq"] = predecessor["seq"]

    return propositions


def main() -> int:
    ap = argparse.ArgumentParser(description="Pass 2 override detector (deterministic)")
    ap.add_argument("--propositions", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    props = json.loads(args.propositions.read_text())
    out = detect_overrides(props)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    overrides = sum(1 for p in out if "overrides_seq" in p)
    print(json.dumps({"count": len(out), "overrides_detected": overrides, "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
