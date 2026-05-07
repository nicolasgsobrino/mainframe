#!/usr/bin/env python3
"""
pass2_template.py — Pass 2 verb-taxonomy template engine (DETERMINISTIC).

Task: T-2026-04-23-002
Plan: AIFIRST-PLAN-3PASS.md §4
Deterministic: yes — zero LLM inference

For each Pass-1 annotation record, render an English proposition via a verb
template. Records whose verb is NOT template-resolvable are emitted with
`proposition_source = 'LLM'` and `proposition = null` so `pass2_llm.py` can
pick them up and produce bounded-context LLM requests.

Per Hard Rule 8 (new, plan §15): LLM calls use temperature=0 structured JSON.
This engine does not call the LLM; it only labels which records need one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Verbs resolvable fully by templates (plan §4 "YES" column).
TEMPLATE_VERBS = {
    "MOVE", "ADD", "SUBTRACT", "MULTIPLY", "COMPUTE",
    "IF", "PERFORM", "CALL", "READ", "WRITE", "OPEN", "CLOSE",
    "INITIALIZE", "SET", "STOP RUN", "GO TO", "GOBACK",
    "ACCEPT", "DISPLAY", "EXIT", "CONTINUE", "DIVIDE", "REWRITE",
    "DELETE", "START", "INSPECT", "MOVE CORRESPONDING",
}

# Verbs that require LLM or partial template (plan §4 "PARTIAL"/"LLM REQUIRED").
LLM_VERBS = {"EXEC CICS", "EXEC SQL"}
PARTIAL_VERBS = {"EVALUATE", "STRING", "UNSTRING"}


def _join(operands: list[str], types: list[str], kinds: set[str]) -> list[str]:
    return [o for o, t in zip(operands, types) if t in kinds]


def template_for(rec: dict) -> tuple[str | None, str]:
    """Return (proposition or None, proposition_source)."""
    verb = rec["verb"]
    ops = rec.get("operands", [])
    types = rec.get("operand_types", [])

    if verb in LLM_VERBS:
        return None, "LLM"
    if verb in PARTIAL_VERBS:
        # Partial templates: emit best-effort stub + mark for LLM refinement.
        if verb == "EVALUATE":
            subj = ops[0] if ops else "expression"
            return f"Branch on value of {subj}", "PARTIAL"
        if verb in {"STRING", "UNSTRING"}:
            return f"Compose or decompose string involving {', '.join(ops[:3])}", "PARTIAL"

    # Deterministic templates.
    if verb == "MOVE":
        sources = _join(ops, types, {"literal", "working-storage"})
        if len(sources) >= 2:
            src, dst = sources[0], sources[-1]
            return f"Set {dst} to {src}", "TEMPLATE"
        return f"Move data between {', '.join(sources)}", "TEMPLATE"
    if verb == "ADD":
        operands = _join(ops, types, {"literal", "working-storage"})
        if len(operands) >= 2:
            return f"Accumulate {operands[0]} into {operands[-1]}", "TEMPLATE"
        return "Accumulate value", "TEMPLATE"
    if verb == "SUBTRACT":
        operands = _join(ops, types, {"literal", "working-storage"})
        if len(operands) >= 2:
            return f"Reduce {operands[-1]} by {operands[0]}", "TEMPLATE"
        return "Subtract value", "TEMPLATE"
    if verb == "MULTIPLY":
        operands = _join(ops, types, {"literal", "working-storage"})
        if len(operands) >= 2:
            return f"Scale {operands[-1]} by factor {operands[0]}", "TEMPLATE"
        return "Multiply value", "TEMPLATE"
    if verb == "DIVIDE":
        operands = _join(ops, types, {"literal", "working-storage"})
        if len(operands) >= 2:
            return f"Divide {operands[-1]} by {operands[0]}", "TEMPLATE"
        return "Divide value", "TEMPLATE"
    if verb == "COMPUTE":
        dst = _join(ops, types, {"working-storage"})
        return (f"Calculate {dst[0]} from an arithmetic expression"
                if dst else "Compute an arithmetic expression"), "TEMPLATE"
    if verb == "IF":
        ctx = rec.get("cfg_branch_context") or "condition"
        return f"When {ctx[3:].strip() if ctx.startswith('IF ') else ctx}", "TEMPLATE"
    if verb == "PERFORM":
        targets = _join(ops, types, {"paragraph"})
        return (f"Execute the {targets[0]} procedure"
                if targets else "Execute a procedure"), "TEMPLATE"
    if verb == "CALL":
        ext = _join(ops, types, {"external-program"})
        return (f"Invoke external program {ext[0]}"
                if ext else "Invoke an external program"), "TEMPLATE"
    if verb == "READ":
        ws = _join(ops, types, {"working-storage", "paragraph"})
        return (f"Retrieve next record from {ws[0]}"
                if ws else "Retrieve next record from file"), "TEMPLATE"
    if verb == "WRITE":
        ws = _join(ops, types, {"working-storage", "paragraph"})
        return (f"Persist {ws[0]} to file"
                if ws else "Persist record to file"), "TEMPLATE"
    if verb == "REWRITE":
        ws = _join(ops, types, {"working-storage", "paragraph"})
        return (f"Update {ws[0]} in place"
                if ws else "Update record in place"), "TEMPLATE"
    if verb == "DELETE":
        return "Delete current record", "TEMPLATE"
    if verb == "START":
        return "Position file cursor at key", "TEMPLATE"
    if verb == "OPEN":
        ws = _join(ops, types, {"working-storage", "paragraph"})
        return (f"Open {', '.join(ws)} for access"
                if ws else "Open file"), "TEMPLATE"
    if verb == "CLOSE":
        ws = _join(ops, types, {"working-storage", "paragraph"})
        return (f"Close {', '.join(ws)}"
                if ws else "Close file"), "TEMPLATE"
    if verb == "INITIALIZE":
        ws = _join(ops, types, {"working-storage"})
        return (f"Reset {ws[0]} to default values"
                if ws else "Reset values"), "TEMPLATE"
    if verb == "SET":
        ws = _join(ops, types, {"working-storage"})
        return (f"Assign a named state to {ws[0]}"
                if ws else "Assign a named state"), "TEMPLATE"
    if verb == "GO TO":
        para = _join(ops, types, {"paragraph"})
        return (f"Transfer control unconditionally to {para[0]}"
                if para else "Transfer control unconditionally"), "TEMPLATE"
    if verb == "STOP RUN":
        return "Terminate program execution", "TEMPLATE"
    if verb == "EXIT":
        return "Exit the current paragraph", "TEMPLATE"
    if verb == "CONTINUE":
        return "Continue without action", "TEMPLATE"
    if verb == "GOBACK":
        return "Return control to caller", "TEMPLATE"
    if verb == "ACCEPT":
        src = _join(ops, types, {"working-storage"})
        return (f"Read external input into {src[0]}"
                if src else "Read external input"), "TEMPLATE"
    if verb == "DISPLAY":
        return "Display output message", "TEMPLATE"
    if verb == "INSPECT":
        ws = _join(ops, types, {"working-storage"})
        return (f"Inspect {ws[0]} contents"
                if ws else "Inspect string contents"), "TEMPLATE"
    if verb == "MOVE CORRESPONDING":
        return "Copy matching subordinate fields", "TEMPLATE"

    # Unknown verb — mark for LLM.
    return None, "LLM"


def proposition_modifies(rec: dict) -> str | None:
    """Return the primary field this statement modifies, if any."""
    verb = rec["verb"]
    ops = rec.get("operands", [])
    types = rec.get("operand_types", [])
    ws_ops = [(o, i) for i, (o, t) in enumerate(zip(ops, types)) if t == "working-storage"]
    if not ws_ops:
        return None
    # Conventions: MOVE/INITIALIZE/ACCEPT/COMPUTE modify the LAST ws operand;
    # ADD/SUBTRACT/MULTIPLY/DIVIDE modify the LAST ws operand; SET modifies
    # the FIRST ws operand.
    if verb == "SET":
        return ws_ops[0][0]
    if verb in {"MOVE", "INITIALIZE", "ACCEPT", "COMPUTE",
               "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE",
               "READ", "WRITE", "REWRITE", "INSPECT", "MOVE CORRESPONDING"}:
        return ws_ops[-1][0]
    return None


def build_propositions(annotations: list[dict]) -> list[dict]:
    """Build Pass-2 proposition records from Pass-1 annotations.

    Each record carries forward enough annotation context for the Pass-2
    LLM branch to build a self-contained request payload without re-reading
    the source file:
      - `raw`             verbatim statement text (from annotation)
      - `operands`        inventory of operand tokens
      - `operand_types`   per-operand classification

    Per review issue #1 (PARTIAL fallback quality): PARTIAL entries carry a
    best-effort template stub as `proposition_stub` but ALSO set
    `needs_llm = True` so the Pass-2 LLM branch refines them into final
    `proposition` text. PARTIAL propositions are treated as provisional
    only — they never ship to Pass 3 without LLM refinement.
    """
    out: list[dict] = []
    for rec in annotations:
        prop, source = template_for(rec)
        entry: dict[str, Any] = {
            "seq": rec["seq"],
            "paragraph": rec["paragraph"],
            "line": rec["line"],
            "verb": rec["verb"],
            "proposition": prop if source == "TEMPLATE" else None,
            "proposition_source": source,
            "modifies": proposition_modifies(rec),
            "cfg_branch_context": rec.get("cfg_branch_context"),
            # Carry forward annotation context so pass2_llm.py can build
            # self-contained request payloads without re-reading .cbl source
            # (addresses T-002 review issue #2: raw field was null in LLM/PARTIAL
            # proposition records).
            "raw": rec.get("raw"),
            "operands": rec.get("operands", []),
            "operand_types": rec.get("operand_types", []),
        }
        if rec.get("operand_unresolved"):
            entry["operand_unresolved"] = True
        # Confidence + needs_llm routing:
        #   TEMPLATE  → confidence=1.0, needs_llm=False (ships as-is to Pass 3)
        #   PARTIAL   → confidence=0.5, needs_llm=True  (stub retained for
        #              audit; LLM branch must refine before Pass 3)
        #   LLM      → confidence=null, needs_llm=True  (no template exists)
        if source == "TEMPLATE":
            entry["confidence"] = 1.0
            entry["needs_llm"] = False
        elif source == "PARTIAL":
            entry["confidence"] = 0.5
            entry["needs_llm"] = True
            entry["proposition_stub"] = prop  # preserved for audit trail
        else:
            entry["confidence"] = None
            entry["needs_llm"] = True
        out.append(entry)
    return out


def selftest() -> int:
    repo = Path(__file__).resolve().parents[1]
    ann_path = repo / "validation" / "pass1" / "COBSWAIT_annotations.json"
    anns = json.loads(ann_path.read_text())
    props = build_propositions(anns)
    assert len(props) == 4, f"expected 4 propositions, got {len(props)}"
    sources = [p["proposition_source"] for p in props]
    assert all(s == "TEMPLATE" for s in sources), f"COBSWAIT should be 100% TEMPLATE; got {sources}"
    assert all(p["proposition"] for p in props), "all COBSWAIT propositions must be non-null"
    print(json.dumps({"selftest": "PASS", "count": len(props), "template_pct": 100, "propositions": [p["proposition"] for p in props]}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pass 2 template engine (deterministic)")
    ap.add_argument("--annotations", type=Path, help="Pass 1 annotations JSON")
    ap.add_argument("--out", type=Path, help="Output propositions JSON")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not (args.annotations and args.out):
        ap.error("--annotations and --out required (or --selftest)")
    anns = json.loads(args.annotations.read_text())
    props = build_propositions(anns)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(props, indent=2))
    stats = {
        "program_id_derived_from_file": args.out.stem,
        "count": len(props),
        "template": sum(1 for p in props if p["proposition_source"] == "TEMPLATE"),
        "partial": sum(1 for p in props if p["proposition_source"] == "PARTIAL"),
        "llm_required": sum(1 for p in props if p["proposition_source"] == "LLM"),
    }
    stats["template_pct"] = round(100.0 * stats["template"] / max(stats["count"], 1), 2)
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
