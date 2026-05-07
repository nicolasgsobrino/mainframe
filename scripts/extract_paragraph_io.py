#!/usr/bin/env python3
# LLM-FREE — Deterministic mutates[]/reads[] derivation from COBOL verbs
# LLM-FREE — and operand classification. No LLM inference.
"""
extract_paragraph_io.py — Derive paragraph-level mutates[] and reads[] for v1.2.

Task: T-2026-04-24-001 (Schema v1.2 — Hercules Byte-Parity Foundation)
Chunk: (d)
RF-07: STANDALONE — reads Pass-1 annotations read-only, does NOT modify pass1_annotate.py.

Authoritative rules (G1-scaffold.md §6.3 / §8.3 + C-3):

    Writers (append to mutates[]):
      receiver of MOVE, INITIALIZE, SET, ADD...TO/GIVING,
        SUBTRACT...FROM/GIVING, MULTIPLY...BY/GIVING, DIVIDE...INTO/GIVING,
        COMPUTE (LHS), STRING...INTO, UNSTRING...INTO

    Readers (append to reads[]):
      sender of MOVE/ADD/SUBTRACT/MULTIPLY/DIVIDE, RHS of COMPUTE,
        all operands of IF, EVALUATE, DISPLAY,
        STRING source operands, UNSTRING source operand

    C-3 SEARCH / SET table rules (mandatory):
      SET <index> TO <value>            → mutates += [<index>]
      SEARCH <table> ... AT END ...     → mutates += [<index-of-table>]
                                           reads   += [<table>]
      SEARCH ALL <table> ... WHEN ...   → mutates += [<index-of-table>]
                                           reads   += [<table>, <WHEN-operands>]
      SEARCH ... WHEN <condition>       → reads   += [<condition operands>]

    Identifier rule (Rule 9):
      All data-name operands emitted fully qualified where possible
      (e.g. COSGN0AI.USERIDL, not bare USERIDL).
      Deduplicate per paragraph preserving first-occurrence source order.
      When an operand's qualified_name is a strict prefix-ancestor of
      another operand qualified in the same statement, drop the ancestor
      (only the specific mutated/read field is emitted).

Output schema:

    {
      "program": str,
      "source_path": str,
      "source_sha256": str,
      "cfg_path": str,
      "cfg_sha256": str,
      "byte_layouts_path": str,
      "byte_layouts_sha256": str,
      "paragraphs": [
        {
          "paragraph": str,
          "classification_source": "annotations",
          "mutates": [{"fd_name": str, "verb": str, "line": int, "raw": str}, ...],
          "reads":   [{"fd_name": str, "verb": str, "line": int, "raw": str}, ...]
        }, ...
      ]
    }

Inputs:
    --source          app/cbl/<PROGRAM>.cbl  (read-only, RF-06)
    --cfg             validation/pass1/<PROGRAM>_annotations.json (read-only, RF-07)
    --byte-layouts    validation/pass1/byte_layouts/<PROGRAM>.json
                      (read-only; source of Rule 9 qualified_name lookup)
    --out             validation/pass1/paragraph_io/<PROGRAM>.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

__LLM_FREE__ = True


# -- Verb classification ---------------------------------------------------

WRITER_VERBS = {
    "MOVE", "INITIALIZE", "SET",
    "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE",
    "COMPUTE", "STRING", "UNSTRING",
    "SEARCH", "SEARCH ALL",
}

READER_VERBS = {
    "MOVE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE",
    "COMPUTE", "IF", "EVALUATE", "DISPLAY",
    "STRING", "UNSTRING",
    "SEARCH", "SEARCH ALL",
}

# COBOL keywords / figurative constants / reserved tokens that appear in
# operand lists but are not data-names. Any operand whose upper-cased form
# is in this set is skipped.
NON_DATA_TOKENS = frozenset({
    "FUNCTION", "UPPER-CASE", "LOWER-CASE", "CURRENT-DATE",
    "NUMVAL", "NUMVAL-C", "TRIM", "REVERSE", "LENGTH",
    "DELIMITED", "REPLACING", "INTO", "TO", "FROM", "BY",
    "GIVING", "SIZE", "WITH", "POINTER", "TALLYING",
    "WHEN", "VARYING", "UNTIL", "AFTER", "BEFORE", "ALL",
    "TRUE", "FALSE",
    "SPACES", "SPACE", "ZEROS", "ZEROES", "ZERO",
    "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES",
    "NULL", "NULLS", "QUOTE", "QUOTES",
    "OF", "IN", "THRU", "THROUGH",
    "ASCENDING", "DESCENDING", "KEY",
    "RECORD", "RECORDS", "EOP",
    "SENTENCE", "DEPENDING", "ON", "AT", "END",
    # COBOL class conditions (operand of IF/EVALUATE as class test)
    "NUMERIC", "ALPHABETIC", "ALPHABETIC-LOWER", "ALPHABETIC-UPPER",
    "POSITIVE", "NEGATIVE", "IS", "NOT", "OR", "AND", "EQUAL", "EQUALS",
    "GREATER", "LESS", "THAN",
})

NON_DATA_TYPES = frozenset({
    "literal", "external-program", "paragraph",
})


def is_literal_token(op: str) -> bool:
    """Return True if op is a literal (quoted string or number)."""
    if not op:
        return True
    if op.startswith("'") or op.startswith('"'):
        return True
    # Numeric (possibly with decimal point or leading minus)
    if re.fullmatch(r"[+\-]?\d+(\.\d+)?", op):
        return True
    return False


def is_data_name(op: str, op_type: str) -> bool:
    """True iff operand is a candidate data-name (not keyword, not literal)."""
    if not op:
        return False
    if op.upper() in NON_DATA_TOKENS:
        return False
    if op_type in NON_DATA_TYPES:
        return False
    if is_literal_token(op):
        return False
    return True


def _operand_in_fragment(op: str, fragment: str) -> bool:
    """Word-boundary match of op within a COBOL source fragment.
    COBOL identifiers: A-Z0-9- (case-insensitive)."""
    pat = r"(?:^|[^A-Za-z0-9\-])" + re.escape(op) + r"(?:[^A-Za-z0-9\-]|$)"
    return re.search(pat, fragment, flags=re.IGNORECASE) is not None


def _split_on_keyword(raw: str, keyword: str):
    """Case-insensitive split on a space-delimited COBOL keyword. Returns
    (before, after) or (None, None) if not found."""
    pat = r"(?:^|\s)" + re.escape(keyword) + r"(?:\s|$)"
    m = re.search(pat, raw, flags=re.IGNORECASE)
    if not m:
        return None, None
    return raw[:m.start()], raw[m.end():]


def classify(verb: str, operands, operand_types, raw: str):
    """Return (mutates_indices, reads_indices) for a single annotation.
    Indices point into the operands list. Classification is position-aware
    using the raw source fragment for TO / GIVING / INTO splits."""
    mutates = []
    reads = []

    verb = (verb or "").upper().strip()
    operands = operands or []
    operand_types = operand_types or []

    # Build parallel list of (idx, name, is_data)
    info = []
    for i, op in enumerate(operands):
        t = operand_types[i] if i < len(operand_types) else ""
        info.append((i, op, is_data_name(op, t)))
    data_indices = [i for (i, op, d) in info if d]

    if verb not in WRITER_VERBS and verb not in READER_VERBS:
        return [], []

    if verb == "MOVE":
        before, after = _split_on_keyword(raw, "TO")
        if after is None:
            # Malformed / continuation-line annotation — conservatively skip
            return [], []
        for (i, op, is_d) in info:
            if not is_d:
                continue
            if _operand_in_fragment(op, after):
                mutates.append(i)
            elif _operand_in_fragment(op, before):
                reads.append(i)
            else:
                # Operand present in neither split (unlikely); default to read
                reads.append(i)
        return mutates, reads

    if verb == "INITIALIZE":
        for i in data_indices:
            mutates.append(i)
        return mutates, reads

    if verb == "SET":
        # SET <receiver...> TO <value>
        # Receivers are ws operands before TO. The value after TO may be
        # TRUE/FALSE/figurative (reads = []) or another data item (read).
        before, after = _split_on_keyword(raw, "TO")
        if before is None:
            # SET <idx> UP BY / DOWN BY <n>: receiver is every ws operand
            for i in data_indices:
                mutates.append(i)
            return mutates, reads
        for (i, op, is_d) in info:
            if not is_d:
                continue
            if _operand_in_fragment(op, before):
                mutates.append(i)
            elif _operand_in_fragment(op, after):
                reads.append(i)
            else:
                mutates.append(i)  # conservative fallback
        return mutates, reads

    if verb in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"}:
        # Split on GIVING first, else on verb-specific "TO"/"FROM"/"BY"/"INTO"
        giving_before, giving_after = _split_on_keyword(raw, "GIVING")
        if giving_after is not None:
            # Everything before GIVING = readers, after = writers
            for (i, op, is_d) in info:
                if not is_d:
                    continue
                if _operand_in_fragment(op, giving_after):
                    mutates.append(i)
                elif _operand_in_fragment(op, giving_before):
                    reads.append(i)
            return mutates, reads

        split_kw = {"ADD": "TO", "SUBTRACT": "FROM",
                    "MULTIPLY": "BY", "DIVIDE": "INTO"}[verb]
        before, after = _split_on_keyword(raw, split_kw)
        if after is None:
            # Malformed / partial — fall back: last ws is writer, rest reads
            if data_indices:
                mutates.append(data_indices[-1])
                reads.extend(data_indices[:-1])
            return mutates, reads
        for (i, op, is_d) in info:
            if not is_d:
                continue
            # For ADD A TO B: B (after "TO") is both read (original) AND
            # written (new value). For precision, annotate B as writer only;
            # the read semantics are implicit in the verb.
            if _operand_in_fragment(op, after):
                mutates.append(i)
            elif _operand_in_fragment(op, before):
                reads.append(i)
        return mutates, reads

    if verb == "COMPUTE":
        # COMPUTE <LHS> = <expr>
        eq_idx = raw.find("=")
        if eq_idx < 0:
            if data_indices:
                mutates.append(data_indices[0])
                reads.extend(data_indices[1:])
            return mutates, reads
        before = raw[:eq_idx]
        after = raw[eq_idx + 1:]
        for (i, op, is_d) in info:
            if not is_d:
                continue
            if _operand_in_fragment(op, before):
                mutates.append(i)
            elif _operand_in_fragment(op, after):
                reads.append(i)
        return mutates, reads

    if verb == "STRING":
        # STRING src1 ... srcn DELIMITED BY ... INTO dest
        before, after = _split_on_keyword(raw, "INTO")
        if after is None:
            # Continuation — sources only (conservative: all ws are reads)
            for i in data_indices:
                reads.append(i)
            return mutates, reads
        for (i, op, is_d) in info:
            if not is_d:
                continue
            if _operand_in_fragment(op, after):
                mutates.append(i)
            elif _operand_in_fragment(op, before):
                reads.append(i)
        return mutates, reads

    if verb == "UNSTRING":
        # UNSTRING src INTO dest1 dest2 ...
        before, after = _split_on_keyword(raw, "INTO")
        if after is None:
            if data_indices:
                reads.append(data_indices[0])
            return mutates, reads
        for (i, op, is_d) in info:
            if not is_d:
                continue
            if _operand_in_fragment(op, after):
                mutates.append(i)
            elif _operand_in_fragment(op, before):
                reads.append(i)
        return mutates, reads

    if verb in {"IF", "EVALUATE", "DISPLAY"}:
        for i in data_indices:
            reads.append(i)
        return mutates, reads

    # C-3 SEARCH / SEARCH ALL
    if verb in {"SEARCH", "SEARCH ALL"}:
        # First operand is the table. SEARCH mutates the associated INDEX
        # while iterating; the annotation format here records the table.
        # All ws operands after the first are read (WHEN operands, etc.)
        if data_indices:
            # Table is read
            reads.append(data_indices[0])
            # Mutates recorded on table (tracks associated INDEXED BY index)
            mutates.append(data_indices[0])
            # WHEN operands → reads
            for i in data_indices[1:]:
                reads.append(i)
        return mutates, reads

    return [], []


# -- Name qualification (Rule 9) ------------------------------------------

def build_qmap(byte_layout: dict) -> dict:
    """Return bare-name -> qualified_name map from byte_layouts JSON.
    On bare-name collision (e.g. FILLER), the name is dropped from the map
    (ambiguous; we emit bare)."""
    qmap = {}
    ambiguous = set()

    def walk(items):
        for it in items or []:
            n = it.get("name")
            q = it.get("qualified_name")
            if n and q:
                if n in qmap and qmap[n] != q:
                    ambiguous.add(n)
                else:
                    qmap[n] = q
            walk(it.get("children"))

    for sec in ("file", "working_storage", "linkage"):
        walk(byte_layout.get("sections", {}).get(sec, []))

    for n in ambiguous:
        qmap.pop(n, None)
    return qmap


def qualify(name: str, qmap: dict) -> str:
    """Return fully-qualified name or bare name if unknown."""
    if not name:
        return name
    return qmap.get(name, name)


def _strip_ancestors(entries):
    """Remove entries whose fd_name is a strict prefix-ancestor of another
    entry in the same statement (keyed by (verb, line, raw)). Preserves
    first-occurrence order within each statement."""
    # Group indices by statement key
    groups = {}
    for idx, e in enumerate(entries):
        key = (e["verb"], e["line"], e["raw"])
        groups.setdefault(key, []).append(idx)

    drop = set()
    for key, idxs in groups.items():
        names = [entries[i]["fd_name"] for i in idxs]
        for i_idx, name_i in zip(idxs, names):
            for j_idx, name_j in zip(idxs, names):
                if i_idx == j_idx:
                    continue
                # name_i is a strict ancestor of name_j iff name_j starts
                # with name_i + "."
                if name_j.startswith(name_i + "."):
                    drop.add(i_idx)
                    break
    return [e for i, e in enumerate(entries) if i not in drop]


def _dedupe_by_fd(entries):
    """Deduplicate by fd_name preserving first-occurrence order."""
    seen = set()
    out = []
    for e in entries:
        if e["fd_name"] in seen:
            continue
        seen.add(e["fd_name"])
        out.append(e)
    return out


# -- Main pipeline --------------------------------------------------------

def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(source_path: Path, cfg_path: Path,
            byte_layouts_path: Path) -> dict:
    source_sha = sha256_of(source_path)
    cfg_sha = sha256_of(cfg_path)
    bl_sha = sha256_of(byte_layouts_path)

    cfg = json.loads(cfg_path.read_text())
    byte_layout = json.loads(byte_layouts_path.read_text())
    qmap = build_qmap(byte_layout)

    proc_anns = [a for a in cfg if a.get("division") == "PROCEDURE"]
    # Stable source order
    proc_anns.sort(key=lambda a: (a.get("line", 0), a.get("seq", 0)))

    # Group by paragraph, preserving first-seen order
    para_order = []
    para_anns = {}
    for a in proc_anns:
        p = a.get("paragraph")
        if not p:
            continue
        if p not in para_anns:
            para_order.append(p)
            para_anns[p] = []
        para_anns[p].append(a)

    paragraphs_out = []
    for p in para_order:
        mutates_entries = []
        reads_entries = []
        for a in para_anns[p]:
            verb = a.get("verb", "")
            operands = a.get("operands") or []
            op_types = a.get("operand_types") or []
            line = a.get("line", 0)
            raw = a.get("raw", "") or ""
            m_idx, r_idx = classify(verb, operands, op_types, raw)
            for i in m_idx:
                op = operands[i]
                fd = qualify(op, qmap)
                mutates_entries.append({
                    "fd_name": fd, "verb": verb,
                    "line": line, "raw": raw,
                })
            for i in r_idx:
                op = operands[i]
                fd = qualify(op, qmap)
                reads_entries.append({
                    "fd_name": fd, "verb": verb,
                    "line": line, "raw": raw,
                })

        # Post-process: strip ancestors per statement, then dedupe per para
        mutates_entries = _strip_ancestors(mutates_entries)
        reads_entries = _strip_ancestors(reads_entries)
        mutates_entries = _dedupe_by_fd(mutates_entries)
        reads_entries = _dedupe_by_fd(reads_entries)

        paragraphs_out.append({
            "paragraph": p,
            "classification_source": "annotations",
            "mutates": mutates_entries,
            "reads": reads_entries,
        })

    return {
        "program": byte_layout.get("program") or source_path.stem,
        "source_path": str(source_path),
        "source_sha256": source_sha,
        "cfg_path": str(cfg_path),
        "cfg_sha256": cfg_sha,
        "byte_layouts_path": str(byte_layouts_path),
        "byte_layouts_sha256": bl_sha,
        "paragraphs": paragraphs_out,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract_paragraph_io.py",
        description="Derive v1.2 mutates[]/reads[] per paragraph (LLM-FREE).",
    )
    parser.add_argument("--source", required=True,
                        help="COBOL source file (read-only)")
    parser.add_argument("--cfg", required=True,
                        help="Pass 1 annotations JSON (read-only, RF-07)")
    parser.add_argument("--byte-layouts", required=True,
                        help="Pass 1 byte_layouts JSON (read-only, Rule 9 qmap)")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    cfg_path = Path(args.cfg)
    bl_path = Path(args.byte_layouts)
    out_path = Path(args.out)

    for p, label in ((source_path, "source"), (cfg_path, "cfg"),
                     (bl_path, "byte-layouts")):
        if not p.is_file():
            print(f"ERROR: {label} path not found: {p}", file=sys.stderr)
            return 2

    out = extract(source_path, cfg_path, bl_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {out_path} ({len(out['paragraphs'])} paragraphs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
