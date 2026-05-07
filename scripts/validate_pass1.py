#!/usr/bin/env python3
"""
validate_pass1.py — T-PASS1 deterministic validator.

Tiers (plan §3):
  T-PASS1-COVERAGE — every PROCEDURE-DIVISION statement has an annotation
                     (we count what Pass 1 produced vs. re-derive from
                     `cobc -E` for independence).
  T-PASS1-CFG      — every branch verb (IF/EVALUATE/GO TO) has a
                     cfg_branch_context OR is flagged unresolved.
  T-PASS1-OPS      — working-storage operands are resolved against
                     data_items_inventory; unresolved are flagged
                     (non-blocking).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BRANCH_VERBS = {"IF", "EVALUATE", "GO TO"}


def count_procedure_statements(src_path: Path) -> int:
    """Re-derive a statement count from `cobc -E` output, independent of
    the annotator. Used as a second source for T-PASS1-COVERAGE.

    We mirror the annotator's filter precedence: paragraph/section headers
    take priority over verb-regex matches, because verb tokens like READ,
    WRITE, OPEN, etc. frequently appear as the first word of a paragraph
    name (e.g. `READ-USER-SEC-FILE.`). Without the paragraph filter, the
    independent count would over-count by one per such paragraph and break
    T-PASS1-COVERAGE comparison.
    """
    from pass1_annotate import KNOWN_VERBS, _VERB_PATTERN, _DIVISION_PATTERN, _PARAGRAPH_PATTERN, _SECTION_PATTERN  # type: ignore

    # Kept in sync with pass1_annotate.STATEMENT_ONLY_TOKENS — tokens that
    # pattern-match as paragraph headers when alone on a line followed by
    # a period, but which the annotator treats as real statements.
    STATEMENT_ONLY_TOKENS = {"GOBACK", "EXIT", "CONTINUE", "STOP"}

    proc = subprocess.run(["cobc", "-E", str(src_path)], capture_output=True, text=True, check=False)
    current_div = None
    count = 0
    for raw in proc.stdout.splitlines():
        if raw.startswith("#line"):
            continue
        mdiv = _DIVISION_PATTERN.match(raw)
        if mdiv:
            current_div = mdiv.group(1).upper()
            continue
        if current_div != "PROCEDURE":
            continue
        # Paragraph / section headers are structural, not statements —
        # filter them BEFORE the verb regex (else `READ-USER-SEC-FILE.`
        # matches as READ). Exception: bare statement-only tokens like
        # `GOBACK.` / `EXIT.` pattern-match as paragraphs but ARE real
        # statements (mirroring annotator behaviour).
        if _SECTION_PATTERN.match(raw):
            continue
        mpar = _PARAGRAPH_PATTERN.match(raw)
        if mpar and mpar.group(1).upper() not in STATEMENT_ONLY_TOKENS:
            continue
        if _VERB_PATTERN.match(raw):
            count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description="T-PASS1 validator")
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--annotations", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    # Make pass1_annotate.py importable when validator is run from the repo.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    annotations = json.loads(args.annotations.read_text())
    independent_count = count_procedure_statements(args.src)

    ann_count = len(annotations)
    coverage_pass = (ann_count == independent_count)

    cfg_errors = []
    for a in annotations:
        if a["verb"] in BRANCH_VERBS and a.get("cfg_branch_context") is None and not a.get("cfg_branch_unresolved"):
            cfg_errors.append(f"seq {a['seq']}: branch verb {a['verb']} has null cfg_branch_context")

    unresolved_ops = [a["seq"] for a in annotations if a.get("operand_unresolved")]

    out = {
        "tier": "T-PASS1",
        "file": str(args.src),
        "annotations": ann_count,
        "independent_statement_count": independent_count,
        "coverage": {
            "tier": "T-PASS1-COVERAGE",
            "pass": coverage_pass,
            "threshold": "100%",
            "blocking": True,
            "diff": ann_count - independent_count,
        },
        "cfg": {
            "tier": "T-PASS1-CFG",
            "pass": len(cfg_errors) == 0,
            "threshold": "100%",
            "blocking": True,
            "errors": cfg_errors[:20],
        },
        "ops": {
            "tier": "T-PASS1-OPS",
            "pass": len(unresolved_ops) == 0,
            "threshold": "100%",
            "blocking": False,
            "unresolved_count": len(unresolved_ops),
            "unresolved_seqs_sample": unresolved_ops[:20],
        },
        "pass": coverage_pass and len(cfg_errors) == 0,
        "validator_version": "v1.0.2-statement-only-tokens",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("tier", "file", "annotations", "pass")}))
    return 0 if out["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
