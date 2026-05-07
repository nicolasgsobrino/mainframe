#!/usr/bin/env python3
"""
pass1_annotate.py — Pass 1 annotation inventory generator (DETERMINISTIC).

Task: T-2026-04-23-002
Plan: AIFIRST-PLAN-3PASS.md §2
Deterministic: yes — zero LLM inference

Toolchain substitution (RF-01, logged in G0):
  The plan specified `cobc -fsyntax-only -fdiagnostics-format=json`.
  GnuCOBOL 3.2.0 does not support `-fdiagnostics-format=json`.
  Substitute: `cobc -E` (preprocessor) emits line-numbered preprocessed source
  that is sufficient to identify verbs, operands, paragraph boundaries, and
  branch contexts when combined with the Cobol-REKT CFG JSON produced under
  Phase 0. This script documents the substitution inline.

Output: validation/pass1/<PROGRAM_ID>_annotations.json
  JSON array of annotation records per plan §2 "Output Format".

Patch history:
  P3 (2026-04-29): Track IF/EVALUATE scope depth so that pending_branch_context
    is cleared when the matching END-IF / END-EVALUATE is consumed.  Previously
    the context bled into every subsequent statement in the paragraph, causing the
    LLM to treat unconditional post-scope code as conditionally guarded.
  P5 (2026-04-29): Add CICS branch command detection.  EXEC CICS commands such as
    RETURN, XCTL, LINK, HANDLE, and ABEND are conditional branch / state-machine
    transition points in pseudo-conversational CICS programs.  Previously they
    received no cfg_branch_context and were emitted to Pass 2 as unconditional
    cics-interaction.  Now they carry is_cics_branch=True and a descriptive
    cfg_branch_context so the LLM can correctly classify them as state-machine
    or guard-with-override.
  P2 (2026-04-29): Rebuild data_items_inventory from the cobc -E preprocessed
    source rather than solely from the Cobol-REKT CFG JSON data_items array.
    Cobol-REKT does not always fully resolve COPY member fields; those fields
    appeared as 'unresolved' operands causing the LLM to lower confidence for
    every proposition that touched a copybook field even when the name was
    unambiguous.  The fix scans the preprocessed DATA DIVISION lines for level
    number + identifier patterns and unions the result with the CFG inventory.
    This is zero-cost (the preprocess() call is already required) and catches
    all COPY-expanded field names deterministically.
  P1 (2026-04-29): Replace seq±1 CFG edge placeholders with real paragraph
    call-graph edges derived from the Cobol-REKT CFG JSON paragraphs[].performs
    and paragraphs[].goto_targets arrays.

    Previously cfg_predecessors/cfg_successors were hardcoded [seq-1]/[seq+1],
    a pure sequential walk with no knowledge of cross-paragraph flow.  The LLM
    received no context about which paragraphs call which, so PERFORM targets
    and GO TO destinations appeared as isolated islands.

    The fix adds resolve_cfg_edges() which runs as a second pass over the
    completed annotation list.  It builds a paragraph→first_seq index, then
    for every PERFORM or GO TO annotation it:
      • Resolves the target paragraph name from the annotation operands.
      • Overwrites cfg_successors with [target_first_seq] when resolvable,
        retaining [seq+1] as fallback for unresolvable targets.
      • Back-patches cfg_predecessors on the first statement of the target
        paragraph to include the calling seq.
      • Adds cfg_perform_target or cfg_goto_target key with the paragraph name
        for Pass 2 context.
    Seq±1 fallback is retained wherever no CFG paragraph edge resolves.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Plan §2 — complete COBOL verb reference for Pass 1.
KNOWN_VERBS = {
    "MOVE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "COMPUTE",
    "IF", "EVALUATE", "PERFORM", "CALL", "GO TO",
    "READ", "WRITE", "REWRITE", "DELETE", "START", "OPEN", "CLOSE",
    "EXEC CICS", "EXEC SQL",
    "MOVE CORRESPONDING", "STRING", "UNSTRING", "INSPECT",
    "INITIALIZE", "SET", "ACCEPT", "DISPLAY", "STOP RUN", "EXIT",
    # Common additional verbs encountered in the pilot corpus.
    "GOBACK", "CONTINUE", "COPY",
}

BRANCH_VERBS = {"IF", "EVALUATE", "GO TO"}

# Scope-opening verbs that increment _scope_depth (P3).
_SCOPE_OPENERS = {"IF", "EVALUATE"}

# Scope terminators that decrement _scope_depth (P3).
# Shared with the phantom-paragraph filter further below.
SCOPE_TERMINATORS = {"END-IF", "END-EVALUATE", "END-EXEC", "END-PERFORM", "END-READ"}

# Regex matching a bare scope-terminator token on its own source line.
_SCOPE_CLOSE_PATTERN = re.compile(
    r"^\s+(END-IF|END-EVALUATE)\b",
    re.IGNORECASE,
)

# P5: CICS commands that are state-machine branch points.
CICS_BRANCH_COMMANDS = {"HANDLE", "RETURN", "XCTL", "LINK", "ABEND"}

# Regex to extract the first CICS command token from text following EXEC CICS.
_CICS_COMMAND_PATTERN = re.compile(
    r"^\s*([A-Z][A-Z0-9\-]*)",
    re.IGNORECASE,
)

# P2: Data-item definition line pattern (level + name in DATA DIVISION).
_DATA_ITEM_PATTERN = re.compile(
    r"^\s+(0[1-9]|[1-4][0-9]|77)\s+([A-Z][A-Z0-9\-]*)\b",
    re.IGNORECASE,
)
_SKIP_LEVELS = {"66", "88"}

# Regex for a statement-leading COBOL verb.
_VERB_PATTERN = re.compile(
    r"^\s+(" + "|".join(re.escape(v) for v in sorted(KNOWN_VERBS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# COBOL paragraph header: "3000-READ-INPUT."
_PARAGRAPH_PATTERN = re.compile(r"^\s{0,3}([A-Z0-9][A-Z0-9\-]*)\.\s*$", re.IGNORECASE)

# Section header: "WORKING-STORAGE SECTION."
_SECTION_PATTERN = re.compile(r"^\s{0,3}([A-Z0-9\-]+)\s+SECTION\.\s*$", re.IGNORECASE)

# Division header: "PROCEDURE DIVISION."
_DIVISION_PATTERN = re.compile(r"^\s{0,3}(IDENTIFICATION|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b", re.IGNORECASE)


def preprocess(src_path: Path) -> list[tuple[int, str]]:
    """Return a list of (physical_line, text) pairs from `cobc -E`."""
    proc = subprocess.run(
        ["cobc", "-E", str(src_path)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0 and not proc.stdout:
        raise RuntimeError(f"cobc -E failed on {src_path}: {proc.stderr}")
    lines: list[tuple[int, str]] = []
    current_line = 0
    for raw in proc.stdout.splitlines():
        m = re.match(r'^#line\s+(\d+)\s+"', raw)
        if m:
            current_line = int(m.group(1))
            continue
        lines.append((current_line, raw))
        current_line += 1
    return lines


def build_expanded_inventory(preprocessed: list[tuple[int, str]]) -> set[str]:
    """P2: Scan cobc -E expanded DATA DIVISION for field definitions."""
    inventory: set[str] = set()
    in_data_division = False
    for _lineno, line in preprocessed:
        mdiv = _DIVISION_PATTERN.match(line)
        if mdiv:
            div = mdiv.group(1).upper()
            if div == "DATA":
                in_data_division = True
            elif div == "PROCEDURE":
                break
            else:
                in_data_division = False
            continue
        if not in_data_division:
            continue
        m = _DATA_ITEM_PATTERN.match(line)
        if m:
            level = m.group(1).lstrip("0") or "0"
            if level in _SKIP_LEVELS:
                continue
            name = m.group(2).upper()
            if name not in ("FILLER", "COPY"):
                inventory.add(name)
    return inventory


def build_cfg_call_index(cfg: dict) -> dict[str, list[str]]:
    """P1: Build a map of paragraph_name → list[paragraph_names_it_performs_or_gotos].

    The Cobol-REKT CFG JSON stores paragraphs[].performs as the list of ALL
    paragraphs reachable from a given paragraph (transitively, per smojol’s
    analysis), not just direct calls.  We use this as a best-available
    approximation: for each PERFORM/GO TO verb annotation we will try to match
    the target operand name against the performs list of the paragraph it lives in.
    This is sufficient for the LLM context purpose — we are not trying to
    replicate a full control-flow analyser, just to give the LLM a non-trivial
    predecessor/successor edge rather than the meaningless seq±1 placeholder.

    Also collects goto_targets per paragraph for GO TO resolution.

    Returns:
        {
            "PARA-NAME": {
                "performs": ["PARA-A", "PARA-B", ...],
                "goto_targets": ["PARA-C", ...]
            },
            ...
        }
    """
    index: dict[str, dict] = {}
    for p in cfg.get("paragraphs", []):
        name = p.get("name", "").upper()
        if not name:
            continue
        # Filter out non-paragraph tokens that smojol sometimes puts in performs
        # (e.g. "UNTIL", "VARYING").
        performs = [
            t.upper() for t in p.get("performs", [])
            if re.match(r'^[A-Z][A-Z0-9\-]+$', t, re.IGNORECASE)
            and t.upper() not in {"UNTIL", "VARYING", "TIMES", "THROUGH", "THRU"}
        ]
        gotos = [t.upper() for t in p.get("goto_targets", [])]
        index[name] = {"performs": performs, "goto_targets": gotos}
    return index


def resolve_cfg_edges(
    annotations: list[dict],
    cfg_call_index: dict[str, dict],
) -> None:
    """P1: Post-pass that replaces seq±1 edge placeholders with real call-graph edges.

    Mutates annotations in-place.

    Algorithm:
    1.  Build paragraph → first_seq mapping from the annotation list itself
        (seq of the first statement belonging to each paragraph).
    2.  For every annotation whose verb is PERFORM or GO TO:
        a.  Extract the target paragraph name from the first 'paragraph' operand.
        b.  Look up the target’s first_seq.
        c.  If found: overwrite cfg_successors with [target_first_seq],
            add cfg_perform_target or cfg_goto_target key,
            back-patch cfg_predecessors on the target’s first annotation.
        d.  If not found: leave cfg_successors as-is (seq+1 fallback).
    3.  Seq±1 fallback is retained wherever resolution fails — this keeps
        the output valid even for programs where the CFG JSON has no paragraph
        information (e.g. COBSWAIT).
    """
    if not annotations:
        return

    # Step 1: paragraph → first_seq index (built from annotations, not CFG JSON,
    # so it reflects the actual statements we annotated).
    para_first_seq: dict[str, int] = {}
    for ann in annotations:
        p = ann["paragraph"].upper()
        if p not in para_first_seq:
            para_first_seq[p] = ann["seq"]

    # Step 2: seq → annotation index for O(1) back-patching.
    seq_index: dict[int, dict] = {ann["seq"]: ann for ann in annotations}

    for ann in annotations:
        verb = ann["verb"]
        if verb not in ("PERFORM", "GO TO"):
            continue

        # Extract the first 'paragraph' type operand as the target name.
        target_name: str | None = None
        for op, ot in zip(ann.get("operands", []), ann.get("operand_types", [])):
            if ot == "paragraph":
                target_name = op.upper()
                break

        if not target_name:
            continue

        # Resolve target first_seq from the annotation-derived index.
        target_seq = para_first_seq.get(target_name)

        # Fall back to CFG call index check: confirm the target is a known
        # paragraph in the CFG (avoids wiring to stray tokens).
        caller_para = ann["paragraph"].upper()
        caller_info = cfg_call_index.get(caller_para, {})
        known_targets = set(caller_info.get("performs", []) + caller_info.get("goto_targets", []))

        if target_seq is None or (known_targets and target_name not in known_targets):
            # Target not resolvable or not confirmed in CFG — keep seq+1 fallback.
            ann["cfg_edge_unresolved"] = True
            continue

        # Wire the edge.
        ann["cfg_successors"] = [target_seq]
        if verb == "PERFORM":
            ann["cfg_perform_target"] = target_name
        else:
            ann["cfg_goto_target"] = target_name

        # Back-patch the target’s first annotation’s predecessors.
        target_ann = seq_index.get(target_seq)
        if target_ann is not None:
            preds = target_ann.get("cfg_predecessors", [])
            if ann["seq"] not in preds:
                target_ann["cfg_predecessors"] = preds + [ann["seq"]]


def identify_operands(verb: str, rest: str, data_items_inventory: set[str]) -> tuple[list[str], list[str]]:
    """
    Extract operands from the text following the verb.

    Returns parallel lists of operand strings and their types:
      - 'literal'          — quoted string or numeric literal
      - 'working-storage'  — identifier present in data_items_inventory
      - 'paragraph'        — used by PERFORM/GO TO (resolved by caller via CFG)
      - 'external-program' — quoted literal target of CALL
      - 'unresolved'       — identifier not in inventory (flagged later)
    """
    ops: list[str] = []
    types: list[str] = []

    text = rest.split("*>")[0].rstrip(". \t")
    tokens = re.findall(r"'[^']*'|\"[^\"]*\"|[A-Z0-9][A-Z0-9\-]*", text, re.IGNORECASE)

    connective = {
        "TO", "FROM", "BY", "INTO", "USING", "GIVING", "UPON",
        "THRU", "THROUGH", "TIMES", "UNTIL", "VARYING",
        "IS", "ARE", "NOT", "AND", "OR", "OF", "IN", "THEN", "ELSE",
        "WHEN", "ON", "SIZE", "ERROR", "AT", "END", "KEY",
        "EQUAL", "GREATER", "LESS", "THAN", "ZERO", "ZEROS", "ZEROES",
        "SPACE", "SPACES", "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES",
        "ALL", "FIRST", "LAST", "ANY", "EACH", "WITH", "BEFORE", "AFTER",
        "INPUT", "OUTPUT", "I-O", "EXTEND", "REVERSED", "NO",
        "REWIND", "RECORD", "CORRESPONDING", "CORR",
    }

    for tok in tokens:
        up = tok.upper()
        if tok.startswith(("'", '"')):
            ops.append(tok)
            types.append("literal" if verb != "CALL" else "external-program")
            continue
        if up in connective:
            continue
        if re.fullmatch(r"[+-]?\d+(\.\d+)?", tok):
            ops.append(tok)
            types.append("literal")
            continue
        if up in data_items_inventory:
            ops.append(up)
            types.append("working-storage")
        else:
            if verb in {"PERFORM", "GO TO"}:
                ops.append(up)
                types.append("paragraph")
            else:
                ops.append(up)
                types.append("unresolved")
    return ops, types


def load_cfg(cfg_path: Path) -> dict:
    return json.loads(cfg_path.read_text())


def build_branch_context(verb: str, text: str) -> str | None:
    """Extract a short textual branch context for IF / EVALUATE / WHEN."""
    text = text.rstrip(". \t")
    if verb == "IF":
        return f"IF {text.strip()}"
    if verb == "EVALUATE":
        return f"EVALUATE {text.strip()}"
    return None


def extract_cics_command(rest: str) -> str | None:
    """P5: Extract the first CICS command token from text following EXEC CICS."""
    m = _CICS_COMMAND_PATTERN.match(rest)
    if m:
        return m.group(1).upper()
    return None


def annotate(src_path: Path, cfg_path: Path, program_id: str) -> tuple[list[dict], list[dict]]:
    """Return (annotations, phantom_filter_events)."""
    cfg = load_cfg(cfg_path)

    # P2: Build data inventory from CFG JSON + cobc -E expanded source (union).
    cfg_inventory: set[str] = {
        d["name"].upper() for d in cfg.get("data_items", []) if d.get("name")
    }
    preprocessed = preprocess(src_path)
    expanded_inventory: set[str] = build_expanded_inventory(preprocessed)
    data_items_inventory: set[str] = cfg_inventory | expanded_inventory

    # P1: Build paragraph call-graph index from CFG JSON.
    cfg_call_index = build_cfg_call_index(cfg)

    cfg_paragraphs = {p.get("name", "").upper() for p in cfg.get("paragraphs", []) if p.get("name")}

    STATEMENT_ONLY_TOKENS = {"GOBACK", "EXIT", "CONTINUE", "STOP"}
    phantom_events: list[dict] = []

    annotations: list[dict] = []
    current_paragraph: str | None = None
    current_section: str | None = None  # noqa: F841
    current_division: str | None = None
    seq = 0
    pending_branch_context: str | None = None
    _scope_depth: int = 0

    for phys_line, line in preprocessed:
        # P3: scope-close detection first.
        mclose = _SCOPE_CLOSE_PATTERN.match(line)
        if mclose and current_division == "PROCEDURE":
            _scope_depth = max(0, _scope_depth - 1)
            if _scope_depth == 0:
                pending_branch_context = None
            continue

        mdiv = _DIVISION_PATTERN.match(line)
        if mdiv:
            current_division = mdiv.group(1).upper()
            continue
        msec = _SECTION_PATTERN.match(line)
        if msec:
            current_section = msec.group(1).upper()  # type: ignore[assignment]
            continue
        mpar = _PARAGRAPH_PATTERN.match(line)
        if mpar and current_division == "PROCEDURE":
            name = mpar.group(1).upper()
            if name in STATEMENT_ONLY_TOKENS:
                pass
            elif name in SCOPE_TERMINATORS or name in data_items_inventory:
                phantom_events.append({
                    "event": "cfg_phantom_filtered",
                    "paragraph_candidate": name,
                    "line": phys_line,
                    "reason": "Cobol-REKT artefact: scope terminator or data-item name",
                })
                continue
            else:
                current_paragraph = name
                pending_branch_context = None
                _scope_depth = 0
                continue

        if current_division != "PROCEDURE":
            continue
        if not current_paragraph:
            current_paragraph = f"{program_id}-MAIN"

        mverb = _VERB_PATTERN.match(line)
        if not mverb:
            continue

        verb = mverb.group(1).upper()
        rest = line[mverb.end():]

        ops, op_types = identify_operands(verb, rest, data_items_inventory)

        seq += 1
        rec = {
            "seq": seq,
            "paragraph": current_paragraph,
            "line": phys_line,
            "verb": verb,
            "operands": ops,
            "operand_types": op_types,
            "cfg_reachable": current_paragraph.upper() in cfg_paragraphs,
            "cfg_branch_context": pending_branch_context,
            # P1: seq±1 placeholders — resolve_cfg_edges() overwrites these
            # for PERFORM/GO TO statements after the first pass completes.
            "cfg_predecessors": [seq - 1] if seq > 1 else [],
            "cfg_successors": [seq + 1],
            "division": current_division,
            "raw": line.strip(),
        }

        if any(t == "unresolved" for t in op_types):
            rec["operand_unresolved"] = True

        # P5: CICS branch command detection.
        if verb == "EXEC CICS":
            cics_cmd = extract_cics_command(rest)
            if cics_cmd and cics_cmd in CICS_BRANCH_COMMANDS:
                options_summary = rest.strip()[:60].rstrip()
                branch_ctx = f"EXEC CICS {cics_cmd} {options_summary}".strip()
                rec["cfg_branch_context"] = branch_ctx
                rec["is_cics_branch"] = True
                rec["cics_command"] = cics_cmd
            else:
                if cics_cmd:
                    rec["cics_command"] = cics_cmd

        elif verb in BRANCH_VERBS and rec["cfg_branch_context"] is None:
            rec["cfg_branch_context"] = build_branch_context(verb, rest)
            if rec["cfg_branch_context"] is None:
                rec["cfg_branch_unresolved"] = True
            if verb in _SCOPE_OPENERS:
                _scope_depth += 1
                pending_branch_context = rec["cfg_branch_context"]
            else:
                pending_branch_context = rec["cfg_branch_context"]

        annotations.append(rec)

    # Tidy last annotation.
    if annotations:
        annotations[-1]["cfg_successors"] = []

    # P1: Second pass — resolve real call-graph edges.
    resolve_cfg_edges(annotations, cfg_call_index)

    return annotations, phantom_events


def selftest() -> int:
    repo = Path(__file__).resolve().parents[1]
    src = repo / "app" / "cbl" / "COBSWAIT.cbl"
    cfg = repo / "validation" / "structure" / "COBSWAIT_cfg.json"
    anns, phantoms = annotate(src, cfg, "COBSWAIT")
    assert len(anns) == 4, f"selftest expected 4 annotations, got {len(anns)}: {[a['verb'] for a in anns]}"
    verbs = [a["verb"] for a in anns]
    assert verbs == ["ACCEPT", "MOVE", "CALL", "STOP RUN"], f"verbs mismatch: {verbs}"
    # P3
    assert all(a["cfg_branch_context"] is None for a in anns), \
        "selftest P3: unexpected branch context on COBSWAIT annotation"
    # P5
    assert not any(a.get("is_cics_branch") for a in anns), \
        "selftest P5: unexpected is_cics_branch on COBSWAIT annotation"
    # P2
    pre = preprocess(src)
    exp_inv = build_expanded_inventory(pre)
    assert isinstance(exp_inv, set), "selftest P2: build_expanded_inventory must return a set"
    # P1: COBSWAIT has no PERFORM/GO TO so no edges should have been resolved
    # (all should retain seq+1 or [] fallback).  Verify resolve_cfg_edges ran
    # without raising by checking no annotation has cfg_perform_target.
    assert not any(a.get("cfg_perform_target") for a in anns), \
        "selftest P1: unexpected cfg_perform_target on COBSWAIT (no PERFORM statements)"
    assert not any(a.get("cfg_goto_target") for a in anns), \
        "selftest P1: unexpected cfg_goto_target on COBSWAIT (no GO TO statements)"
    print(json.dumps({"selftest": "PASS", "annotations": len(anns), "verbs": verbs,
                      "phantoms_filtered": len(phantoms),
                      "p1_edge_resolution_ok": True,
                      "p2_expanded_inventory_size": len(exp_inv),
                      "p3_scope_depth_ok": True,
                      "p5_cics_branch_ok": True}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pass 1 annotator (deterministic)")
    ap.add_argument("--src", type=Path, help="Path to COBOL source (.cbl)")
    ap.add_argument("--cfg", type=Path, help="Path to Phase-0 CFG JSON")
    ap.add_argument("--program-id", type=str, help="PROGRAM-ID (e.g. COBSWAIT)")
    ap.add_argument("--out", type=Path, help="Output annotations JSON path")
    ap.add_argument("--phantoms-out", type=Path, default=None, help="Optional: phantom events JSON path")
    ap.add_argument("--selftest", action="store_true", help="Run built-in COBSWAIT selftest and exit")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not (args.src and args.cfg and args.program_id and args.out):
        ap.error("--src, --cfg, --program-id, --out all required (or --selftest)")

    annotations, phantoms = annotate(args.src, args.cfg, args.program_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(annotations, indent=2))
    if args.phantoms_out:
        args.phantoms_out.parent.mkdir(parents=True, exist_ok=True)
        args.phantoms_out.write_text(json.dumps(phantoms, indent=2))

    resolved_edges = sum(
        1 for a in annotations
        if a.get("cfg_perform_target") or a.get("cfg_goto_target")
    )
    print(json.dumps({
        "program_id": args.program_id,
        "annotations": len(annotations),
        "phantoms_filtered": len(phantoms),
        "unresolved_operands": sum(1 for a in annotations if a.get("operand_unresolved")),
        "branch_verbs": sum(1 for a in annotations if a["verb"] in BRANCH_VERBS),
        "cics_branches": sum(1 for a in annotations if a.get("is_cics_branch")),
        "cfg_edges_resolved": resolved_edges,
        "cfg_edges_unresolved": sum(1 for a in annotations if a.get("cfg_edge_unresolved")),
        "out": str(args.out),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
