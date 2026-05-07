#!/usr/bin/env python3
# LLM-FREE — Deterministic paragraph fall-through derivation from COBOL source
# LLM-FREE — and Pass 1 annotations. No LLM inference.
"""
extract_fallthrough.py — Derive paragraph-level fall-through[] for v1.2.

Task: T-2026-04-24-001 (Schema v1.2 — Hercules Byte-Parity Foundation)
Gate: G2, chunk (c).

Authoritative rule (verbatim from G1-scaffold.md §6.2 / §8.2):

    For each paragraph P, inspect the LAST verb emitted in P:
      GO TO ...                 → terminator = goto
      STOP RUN                  → terminator = stop-run
      GOBACK                    → terminator = goback
      EXIT PROGRAM              → terminator = explicit-exit
      EXEC CICS RETURN END-EXEC → terminator = cics-return
      EXEC CICS XCTL    END-EXEC→ terminator = cics-xctl
      (none of above)           → terminator = implicit,
                                  falls_through_to = next-paragraph-in-source-order
      Last paragraph in program with no explicit terminator
                                → terminator = implicit-end-of-program

C-5 (RF-04) mandatory assertion:
    For every consecutive paragraph pair (P_n, P_{n+1}) in source order:
        P_{n+1}.line > P_n.line
    If this guard fails anywhere, emit BLOCKED and halt.

EXEC CICS classification rule (chunk-(c) authorization feedback):
    The user directive is to read `raw` from Pass 1 annotations (not just
    `verb`) when classifying the terminator. Pass 1 raw is line-bounded:
    for multi-line EXEC CICS blocks the operation keyword (RETURN/XCTL/
    LINK/SEND/...) may live on a continuation line and be missing from
    raw. We first try `raw`; if the operation keyword is not present
    there, we read the COBOL source at the annotation's line number and
    scan forward to the next END-EXEC (or sentinel), extracting the
    first keyword after 'EXEC CICS'. This is still LLM-FREE and
    deterministic — we never inspect semantic content, only the keyword
    immediately following EXEC CICS.

Inputs:
  --source app/cbl/<PROGRAM>.cbl   read-only COBOL source (RF-06)
  --cfg    validation/pass1/<PROGRAM>_annotations.json (RF-07 read-only)
  --out    validation/pass1/fallthrough/<PROGRAM>.json

Output: JSON object with elements:
    {"program": str, "source_sha256": str,
     "paragraphs": [
        {"paragraph": str, "first_line": int, "last_line": int,
         "terminator": str, "falls_through_to": str|None, "last_verb": str,
         "last_raw": str, "classification_source": "raw"|"source_scan"|"annotations"}
     ],
     "c5_assertion": "PASS"|"BLOCKED",
     "c5_violations": [{"prev":..., "next":..., "prev_line":..., "next_line":...}]
    }

Standalone — this script DOES NOT modify scripts/pass1_annotate.py (RF-07).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

__LLM_FREE__ = True


# ---------------------------------------------------------------------------
# Terminator classification
# ---------------------------------------------------------------------------

# The first keyword after 'EXEC CICS' that determines terminator classification.
# Note: COBSWAIT has no CICS; COSGN00C / COMEN01C exercise this code path.
CICS_TERMINATOR_OPS = {
    "RETURN": "cics-return",
    "XCTL": "cics-xctl",
}


def _classify_exec_cics(raw: str, line_no: int, source_lines: list[str]) -> tuple[str | None, str]:
    """Return (terminator_or_None, classification_source).

    1. First try the annotation's `raw` field — look for the first keyword
       after 'EXEC CICS' (case-insensitive).
    2. If not present (e.g. operation lives on a continuation line), scan
       the COBOL source starting at `line_no` (1-based), reading columns
       8..72 and ignoring comment lines, until we see END-EXEC or a period
       that terminates the sentence.  Extract the first non-'EXEC'/'CICS'
       keyword.
    3. If no RETURN/XCTL is found, the EXEC CICS block is some other CICS
       command (SEND / RECEIVE / INQUIRE / ASSIGN / ...).  Per §8.2 these
       are NOT listed terminators, so the paragraph's terminator degrades
       to `implicit`. Return (None, source_scan) so the caller treats it
       that way.
    """
    m = re.search(r"\bEXEC\s+CICS\s+([A-Z][A-Z0-9\-]*)", raw, re.IGNORECASE)
    if m:
        kw = m.group(1).upper()
        if kw in CICS_TERMINATOR_OPS:
            return CICS_TERMINATOR_OPS[kw], "raw"
        # Non-terminator CICS op found in raw. No need to scan.
        return None, "raw"

    # Raw has only 'EXEC CICS' with no operation keyword.  Scan the source.
    # Column-aware: take cols 8..72, skip comment indicators.
    i = line_no - 1  # 0-based into source_lines
    words: list[str] = []
    while i < len(source_lines) and i < line_no + 15:  # bounded forward scan
        raw_line = source_lines[i]
        # Strip sequence area / indicator per COBOL fixed-format rules.
        if len(raw_line) >= 7 and raw_line[6] in ("*", "/"):
            i += 1
            continue
        area = raw_line[7:72] if len(raw_line) > 7 else raw_line
        up = area.upper()
        # Stop at END-EXEC or a period that ends the sentence.
        if "END-EXEC" in up:
            # Grab the tokens collected up to here (if any), plus anything on
            # this line before END-EXEC.
            pre = up.split("END-EXEC", 1)[0]
            for tok in re.findall(r"[A-Z][A-Z0-9\-]*", pre):
                if tok not in ("EXEC", "CICS"):
                    words.append(tok)
            break
        for tok in re.findall(r"[A-Z][A-Z0-9\-]*", up):
            if tok not in ("EXEC", "CICS"):
                words.append(tok)
        i += 1

    if not words:
        return None, "source_scan"
    op = words[0]
    if op in CICS_TERMINATOR_OPS:
        return CICS_TERMINATOR_OPS[op], "source_scan"
    return None, "source_scan"


# GO TO / STOP RUN / GOBACK / EXIT PROGRAM detection via verb + raw.
# The Pass-1 verb field is reliable for these; raw is only needed to
# distinguish 'EXIT' (paragraph EXIT) from 'EXIT PROGRAM'.
def _classify_terminator(verb: str, raw: str, line_no: int, source_lines: list[str]) -> tuple[str | None, str]:
    v = verb.upper().strip()
    r = raw.upper().strip()
    if v == "GO TO" or v == "GOTO" or r.startswith("GO TO ") or r.startswith("GOTO "):
        return "goto", "annotations"
    if v == "STOP RUN" or "STOP RUN" in r:
        return "stop-run", "annotations"
    if v == "GOBACK" or r.startswith("GOBACK"):
        return "goback", "annotations"
    if "EXIT PROGRAM" in r:
        return "explicit-exit", "annotations"
    if v == "EXEC CICS" or r.startswith("EXEC CICS"):
        return _classify_exec_cics(raw, line_no, source_lines)
    return None, "annotations"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run(source_path: Path, cfg_path: Path, out_path: Path) -> dict:
    source_bytes = source_path.read_bytes()
    source_lines = source_path.read_text(encoding="utf-8").splitlines()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    # Pass-1 annotations are a flat list of dicts with keys
    # seq, paragraph, line, verb, raw, division, operands, ...
    # We build per-paragraph first/last in source (seq) order, preserving
    # the arrival order of first occurrence.
    first: dict[str, dict] = {}
    last: dict[str, dict] = {}
    for e in cfg:
        if e.get("division") != "PROCEDURE":
            continue
        p = e["paragraph"]
        if p not in first:
            first[p] = e
        last[p] = e

    # Source order = ascending first.line.
    ordered = sorted(first.keys(), key=lambda p: first[p]["line"])

    # C-5 source-order guard: line[n+1] > line[n] for consecutive paragraphs.
    violations = []
    for i in range(len(ordered) - 1):
        p_prev = ordered[i]
        p_next = ordered[i + 1]
        ln_prev = first[p_prev]["line"]
        ln_next = first[p_next]["line"]
        if ln_next <= ln_prev:
            violations.append(
                {
                    "prev": p_prev,
                    "next": p_next,
                    "prev_line": ln_prev,
                    "next_line": ln_next,
                }
            )
    c5 = "BLOCKED" if violations else "PASS"

    paragraphs_out: list[dict] = []
    for i, p in enumerate(ordered):
        le = last[p]
        fe = first[p]
        verb = le["verb"]
        raw = le["raw"]
        ln = le["line"]
        terminator, clsrc = _classify_terminator(verb, raw, ln, source_lines)

        is_last = (i == len(ordered) - 1)
        if terminator is None:
            if is_last:
                terminator = "implicit-end-of-program"
                falls_to = None
            else:
                terminator = "implicit"
                falls_to = ordered[i + 1]
        else:
            falls_to = None

        paragraphs_out.append(
            {
                "paragraph": p,
                "first_line": fe["line"],
                "last_line": ln,
                "terminator": terminator,
                "falls_through_to": falls_to,
                "last_verb": verb,
                "last_raw": raw,
                "classification_source": clsrc,
            }
        )

    out = {
        "program": source_path.stem,
        "source_path": str(source_path),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "cfg_path": str(cfg_path),
        "cfg_sha256": hashlib.sha256(cfg_path.read_bytes()).hexdigest(),
        "paragraphs": paragraphs_out,
        "c5_assertion": c5,
        "c5_violations": violations,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    # If C-5 failed, the extractor still writes the report so the validator
    # can see the evidence, but exits non-zero so the caller halts per §6.2.
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract_fallthrough.py",
        description="Derive v1.2 fall_through[] per paragraph (LLM-FREE).",
    )
    parser.add_argument("--source", required=True, help="COBOL source file (read-only)")
    parser.add_argument(
        "--cfg", required=True,
        help="Pass 1 annotations JSON (read-only, RF-07)",
    )
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args(argv)

    source = Path(args.source)
    cfg = Path(args.cfg)
    out = Path(args.out)
    if not source.exists():
        print(f"ERROR: source not found: {source}", file=sys.stderr); return 2
    if not cfg.exists():
        print(f"ERROR: cfg annotations not found: {cfg}", file=sys.stderr); return 2
    result = run(source, cfg, out)
    # C-5 is a HARD halt: exit non-zero if BLOCKED, so that the caller can
    # treat the chunk as failed per §6.2.
    if result["c5_assertion"] == "BLOCKED":
        print("BLOCKED: C-5 source-order guard violated", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
