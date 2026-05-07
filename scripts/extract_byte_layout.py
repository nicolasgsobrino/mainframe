#!/usr/bin/env python3
# LLM-FREE — This extractor performs deterministic derivation from COBOL source
# LLM-FREE — and existing CFG JSON. No LLM inference. No network calls.
"""
extract_byte_layout.py — Derive v1.2 byte_layout[] from COBOL DATA DIVISION.

Task: T-2026-04-24-001 (Schema v1.2 — Hercules Byte-Parity Foundation)
Gate: G2, chunk (b).

Authoritative derivation rules (verbatim from G1-scaffold.md §6.1, §8.1, C-2):

    PIC / USAGE byte ladder:
      X(n)          / default|DISPLAY           -> display            n bytes
      9(n)          / default|DISPLAY           -> zoned-decimal      n bytes
      9(n)          / COMP-3 | PACKED-DECIMAL   -> packed-decimal     ceil((n+1)/2)
      9(n)          / COMP | BINARY | COMP-4    -> binary             2 if n<=4 else 4 if n<=9 else 8
      9(n)          / COMP-5                    -> binary *native*    same as COMP
      9(n)          / COMP-1                    -> float              4
      9(n)          / COMP-2                    -> float              8
      S9(n)V9(m)    / COMP-3                    -> packed-decimal     ceil((n+m+1)/2)
      POINTER       / -                         -> pointer            8

    Aggregation:
      Group items         -> total_bytes = sum(child.total_bytes + child.slack_bytes_before)
      OCCURS n            -> total_bytes = element.total_bytes * n
      OCCURS n TO m DEPENDING ON
                          -> emit total_bytes_min AND total_bytes_max + variable_length: true
      REDEFINES target    -> total_bytes = target.total_bytes (no new storage)

    C-2 SYNC / SYNCHRONIZED:
      Force alignment halfword(2) | word(4) | doubleword(8). Emit
      slack_bytes_before on the SYNC'd elementary item so that
      (cumulative_offset + slack_bytes_before) % alignment == 0.
      Group total INCLUDES the slack: sum(slack_bytes_before + child.total_bytes).

    Rule 9 (fully qualified names):
      Emit qualified_name as <parent>.<child>...; root is the name itself.

    COMP-5 note (per user G1 feedback):
      Schema `encoding` enum has `binary` (no `binary-native`). We emit
      encoding == "binary" for COMP-5 and flag comp5_native: true on the item
      to preserve the z/OS native-byte-order assumption. See RF-01.

Inputs:
  --source       app/cbl/<PROGRAM>.cbl (read-only, RF-06)
  --cfg          validation/pass1/<PROGRAM>_annotations.json (read-only, RF-07)
                 (accepted but not required; byte_layout is derived from source)
  --copybook-dir app/cpy (default) — copybook search root
  --out          validation/pass1/byte_layouts/<PROGRAM>.json

Output JSON:
  {
    "program": "<PROGRAM>",
    "source_sha256": "<sha>",
    "sections": {
      "file": [ <record> ... ],              # FD-attached 01/77 records
      "working_storage": [ <record> ... ],
      "linkage": [ <record> ... ]
    },
    "totals": {
      "working_storage_bytes": <int>,        # for §8.5 memory_model
      "linkage_bytes": <int>                 # for §8.5 memory_model
    }
  }

Each <record> has:
  level, name, qualified_name, section, pic?, usage?, encoding?,
  total_bytes, total_bytes_min?, total_bytes_max?,
  variable_length?, redefines?, occurs?, occurs_min?, occurs_max?,
  occurs_depending_on?, sync?, alignment?, slack_bytes_before?,
  comp5_native?, fd?, children: [...]

Hard constraints:
  - NO LLM inference. NO network. Deterministic.
  - READ-ONLY: app/cbl/, translations/baseline/, gold-candidate/, baseline-v1.1/.
  - All emitted names are fully qualified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

__LLM_FREE__ = True

# ---------------------------------------------------------------------------
# COBOL source normalization
# ---------------------------------------------------------------------------

# Area A starts at col 8 (index 7), Area B continues through col 72 (index 71).
# Col 7 (index 6) is the indicator area: '*' or '/' = comment, '-' = continuation.
# Cols 1-6 (indices 0..5) are sequence area, ignored.
# Cols 73-80 (indices 72..79) are identification area, ignored.

COPY_RE = re.compile(r"^\s*COPY\s+([A-Z0-9\-_.]+)\s*\.\s*$", re.IGNORECASE)
EJECT_RE = re.compile(r"^\s*(EJECT|SKIP1|SKIP2|SKIP3)\s*\.?\s*$", re.IGNORECASE)
DIVISION_RE = re.compile(r"^\s*([A-Z\-]+)\s+DIVISION\s*\.?\s*$", re.IGNORECASE)
SECTION_RE = re.compile(r"^\s*([A-Z\-]+(?:\s+[A-Z\-]+)?)\s+SECTION\s*\.?\s*$", re.IGNORECASE)


def _strip_area(line: str) -> tuple[str, str]:
    """Return (indicator, area_text) stripping seq area and id area.

    indicator is the single character at column 7 (' ' normally, '*' comment,
    '-' continuation, '/' page-eject comment). area_text is columns 8..72.
    Short lines are handled gracefully.
    """
    # Drop trailing newline / whitespace
    raw = line.rstrip("\n").rstrip("\r")
    # If the line has fewer than 7 chars, treat whole thing as free-form.
    if len(raw) < 7:
        return (" ", raw.lstrip())
    indicator = raw[6]
    area = raw[7:72] if len(raw) > 7 else ""
    return (indicator, area)


def _load_source(path: Path) -> list[tuple[int, str]]:
    """Return list of (original_line_number_1based, area_text) with comments
    removed. Continuation lines are collapsed into the preceding token, which
    is handled at tokenization time below.
    """
    out: list[tuple[int, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            indicator, area = _strip_area(line)
            if indicator in ("*", "/"):
                continue
            # Preserve leading spaces to distinguish continuation handling.
            if indicator == "-":
                # Continuation: the area begins where a non-blank starts.
                out.append((i, "\x01" + area))  # \x01 marks continuation
            else:
                out.append((i, area))
    return out


def _expand_copybooks(
    lines: list[tuple[int, str]],
    copy_dirs: list[Path],
    visited: set[str] | None = None,
) -> list[tuple[int, str]]:
    """Expand COPY statements by inlining copybook content. Recursive with
    a visited set to prevent cycles.
    """
    if visited is None:
        visited = set()
    expanded: list[tuple[int, str]] = []
    for lineno, text in lines:
        m = COPY_RE.match(text)
        if m:
            name = m.group(1).rstrip(".").upper()
            if name in visited:
                # Cycle — skip silently. (Same rationale as the not-found
                # case: emitting placeholder text can poison sentence boundaries.)
                continue
            found = None
            for d in copy_dirs:
                for ext in (".cpy", ".CPY", ".cbl", ".CBL"):
                    cand = d / (name + ext)
                    if cand.exists():
                        found = cand
                        break
                if found:
                    break
            if found is None:
                # Copybook not found — skip entirely. Emitting any placeholder
                # text here would risk absorbing into the next sentence and
                # corrupting section/division detection. A missing copybook is
                # itself a BLOCK condition that downstream validators will
                # catch via missing qualified names.
                continue
            sub = _load_source(found)
            sub = _expand_copybooks(sub, copy_dirs, visited | {name})
            expanded.extend(sub)
        else:
            expanded.append((lineno, text))
    return expanded


def _join_continuations(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Merge continuation (\x01) lines into the prior line preserving the
    origin line number of the start of the sentence."""
    out: list[tuple[int, str]] = []
    for lineno, text in lines:
        if text.startswith("\x01"):
            if out:
                prior_ln, prior = out[-1]
                out[-1] = (prior_ln, prior + " " + text[1:].lstrip())
            else:
                out.append((lineno, text[1:].lstrip()))
        else:
            out.append((lineno, text))
    return out


def _split_sentences(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Split into period-terminated sentences. Each sentence carries the line
    number of its FIRST token.
    """
    sentences: list[tuple[int, str]] = []
    cur_ln: int | None = None
    buf: list[str] = []
    for lineno, text in lines:
        stripped = text.strip()
        if not stripped:
            continue
        if cur_ln is None:
            cur_ln = lineno
        # Split on periods but keep track of residual text after each period.
        # A period ends a sentence only when followed by whitespace or EOL.
        idx = 0
        while idx < len(stripped):
            dot = stripped.find(".", idx)
            if dot == -1:
                buf.append(stripped[idx:])
                idx = len(stripped)
                break
            # accept as terminator
            piece = stripped[idx:dot]
            buf.append(piece)
            sent = " ".join(s for s in buf if s).strip()
            if sent:
                sentences.append((cur_ln, sent))
            buf = []
            idx = dot + 1
            cur_ln = None
            # Skip any whitespace after the period in the same line.
            while idx < len(stripped) and stripped[idx] in " \t":
                idx += 1
            if idx < len(stripped):
                cur_ln = lineno
        # carry buf to next line if no terminator yet
    if buf:
        sent = " ".join(s for s in buf if s).strip()
        if sent:
            sentences.append((cur_ln or 0, sent))
    return sentences


# ---------------------------------------------------------------------------
# DATA DIVISION item parsing
# ---------------------------------------------------------------------------

PIC_RE = re.compile(
    r"\bPIC(?:TURE)?\s+(?:IS\s+)?(?P<pic>[^\s.]+(?:\([0-9]+\)[^\s.]*)*)",
    re.IGNORECASE,
)
USAGE_RE = re.compile(
    r"\b(?:USAGE\s+(?:IS\s+)?)?"
    r"(?P<usage>COMP-[1-5X]|COMP(?!\-)|COMPUTATIONAL-[1-5X]|COMPUTATIONAL(?!\-)|"
    r"BINARY|PACKED-DECIMAL|DISPLAY|POINTER|INDEX)\b",
    re.IGNORECASE,
)
OCCURS_FIXED_RE = re.compile(
    r"\bOCCURS\s+(?P<n>\d+)\s+TIMES\b", re.IGNORECASE,
)
OCCURS_VAR_RE = re.compile(
    r"\bOCCURS\s+(?P<min>\d+)\s+TO\s+(?P<max>\d+)\s+TIMES"
    r"(?:\s+DEPENDING\s+ON\s+(?P<dep>[A-Z0-9\-_]+))?",
    re.IGNORECASE,
)
REDEFINES_RE = re.compile(r"\bREDEFINES\s+(?P<target>[A-Z0-9\-_]+)", re.IGNORECASE)
SYNC_RE = re.compile(r"\b(SYNC|SYNCHRONIZED)(?:\s+(LEFT|RIGHT))?", re.IGNORECASE)
SIGN_SEP_RE = re.compile(
    r"\bSIGN\s+(?:IS\s+)?(LEADING|TRAILING)?\s*(SEPARATE(?:\s+CHARACTER)?)",
    re.IGNORECASE,
)

# Level number prefix at start of sentence: `05 NAME` or `01 NAME` etc.
LEVEL_RE = re.compile(
    r"^\s*(?P<level>\d{1,2})\s+(?P<name>[A-Z0-9\-_]+)\b", re.IGNORECASE,
)
FD_RE = re.compile(r"^\s*FD\s+(?P<name>[A-Z0-9\-_]+)\b", re.IGNORECASE)


def _parse_pic_bytes(pic: str, usage: str) -> tuple[int, str]:
    """Return (bytes, encoding) for an elementary item.

    pic is a PIC clause string e.g. 'X(8)', '9(11)', 'S9(10)V99', 'S9(9)',
    '9(4)', 'X', '999'. usage is 'DISPLAY', 'COMP', 'BINARY', 'COMP-3',
    'COMP-4', 'COMP-5', 'COMP-1', 'COMP-2', 'PACKED-DECIMAL'.
    """
    u = usage.upper()
    # normalize synonyms
    if u in ("COMPUTATIONAL", "COMPUTATIONAL-4", "COMP-4", "COMP"):
        u = "COMP"
    elif u in ("COMPUTATIONAL-3", "PACKED-DECIMAL"):
        u = "COMP-3"
    elif u in ("COMPUTATIONAL-5",):
        u = "COMP-5"
    elif u in ("COMPUTATIONAL-1",):
        u = "COMP-1"
    elif u in ("COMPUTATIONAL-2",):
        u = "COMP-2"
    elif u in ("BINARY",):
        u = "COMP"

    # Special USAGE without PIC:
    if u == "COMP-1":
        return 4, "float"
    if u == "COMP-2":
        return 8, "float"

    # Count digits / chars in PIC
    def _count(symbol: str) -> int:
        """Count occurrences of `symbol` in pic, expanding (n) repetitions."""
        total = 0
        i = 0
        while i < len(pic):
            c = pic[i]
            if c.upper() == symbol.upper():
                # look ahead for (n)
                if i + 1 < len(pic) and pic[i + 1] == "(":
                    j = pic.find(")", i + 1)
                    if j != -1:
                        total += int(pic[i + 2 : j])
                        i = j + 1
                        continue
                total += 1
            i += 1
        return total

    n_nine = _count("9")  # digits before/after V
    n_x = _count("X")
    n_a = _count("A")
    # S/V/P don't occupy storage themselves (V is implied decimal point).
    # SIGN SEPARATE character (+1) is handled by the caller via flag.
    digits = n_nine

    if n_x > 0:
        # alphanumeric
        return n_x, "display"
    if n_a > 0:
        # alphabetic
        return n_a, "display"

    if digits == 0:
        # no PIC? treat as 0 bytes (group)
        return 0, "group"

    if u == "COMP-3":
        return math.ceil((digits + 1) / 2), "packed-decimal"
    if u == "COMP":
        if digits <= 4:
            return 2, "binary"
        if digits <= 9:
            return 4, "binary"
        return 8, "binary"
    if u == "COMP-5":
        if digits <= 4:
            return 2, "binary"  # Note: COMP-5 is native byte order; flag separately.
        if digits <= 9:
            return 4, "binary"
        return 8, "binary"
    # DISPLAY numeric = zoned decimal
    return digits, "zoned-decimal"


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------


class Item(dict):
    """Simple dict wrapper to make construction ergonomic."""


def _parse_item(sentence: str, lineno: int) -> dict | None:
    """Parse a single level-prefixed data description entry into an Item dict.
    Returns None if the sentence is not a level entry (e.g. 66 or 88 are
    filtered upstream; blank lines already dropped).
    """
    m = LEVEL_RE.match(sentence)
    if not m:
        return None
    level = int(m.group("level"))
    name = m.group("name").upper()
    rest = sentence[m.end() :]
    # skip 88 (condition name), 66 (RENAMES) here — caller must also filter
    if level in (88, 66):
        return None

    item: dict = {
        "level": level,
        "name": name,
        "line": lineno,
    }

    # REDEFINES
    mr = REDEFINES_RE.search(rest)
    if mr:
        item["redefines"] = mr.group("target").upper()

    # OCCURS
    mov = OCCURS_VAR_RE.search(rest)
    if mov:
        item["occurs_min"] = int(mov.group("min"))
        item["occurs_max"] = int(mov.group("max"))
        if mov.group("dep"):
            item["occurs_depending_on"] = mov.group("dep").upper()
        item["variable_length"] = True
    else:
        mof = OCCURS_FIXED_RE.search(rest)
        if mof:
            item["occurs"] = int(mof.group("n"))

    # SYNC / SYNCHRONIZED
    ms = SYNC_RE.search(rest)
    if ms:
        item["sync"] = True

    # USAGE
    mu = USAGE_RE.search(rest)
    if mu:
        usage = mu.group("usage").upper()
    else:
        usage = "DISPLAY"
    item["usage"] = usage

    # PIC
    mp = PIC_RE.search(rest)
    if mp:
        item["pic"] = mp.group("pic").upper().rstrip(".")

    # SIGN SEPARATE — flag only (affects byte count for zoned decimal)
    mss = SIGN_SEP_RE.search(rest)
    if mss:
        item["sign_separate"] = True

    return item


def _build_tree(items: list[dict]) -> list[dict]:
    """Build the parent/child tree from a flat sequence of level-prefixed
    items. Uses the classic COBOL stack rule: an item's parent is the nearest
    preceding item with a STRICTLY SMALLER level number.
    """
    roots: list[dict] = []
    stack: list[dict] = []
    for it in items:
        it.setdefault("children", [])
        while stack and stack[-1]["level"] >= it["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(it)
        else:
            roots.append(it)
        stack.append(it)
    return roots


# ---------------------------------------------------------------------------
# Byte size computation (with SYNC slack + REDEFINES + OCCURS + ODO)
# ---------------------------------------------------------------------------

_ALIGNMENT_FOR_USAGE = {
    "COMP": {2: "halfword", 4: "word", 8: "doubleword"},
    "COMP-5": {2: "halfword", 4: "word", 8: "doubleword"},
    "COMP-1": {4: "word"},
    "COMP-2": {8: "doubleword"},
    "POINTER": {8: "doubleword"},
}


def _align_of(usage: str, size: int) -> tuple[int, str]:
    """Return (boundary_bytes, alignment_name) for a SYNC'd elementary item.
    Falls back to halfword(2) for anything unknown — z/OS COBOL default."""
    u = usage.upper()
    if u in ("BINARY", "COMPUTATIONAL", "COMPUTATIONAL-4", "COMP-4"):
        u = "COMP"
    if u in ("PACKED-DECIMAL",):
        u = "COMP-3"
    if u == "COMP-3":
        # SYNC on COMP-3 is non-standard on z/OS; treat as halfword.
        return 2, "halfword"
    table = _ALIGNMENT_FOR_USAGE.get(u)
    if not table:
        return 2, "halfword"
    if size in table:
        return size, table[size]
    return 2, "halfword"


def _size_item(
    item: dict,
    by_name: dict[str, dict],
    cumulative_offset: int = 0,
) -> None:
    """Compute total_bytes / total_bytes_min / total_bytes_max / slack_bytes_before
    IN PLACE on the item and all descendants.

    cumulative_offset is the current offset inside the PARENT group (after prior
    siblings have been placed) — used for SYNC slack calculation.
    """
    children: list[dict] = item.get("children", [])

    # Resolve REDEFINES first — uses the target's total_bytes.
    if "redefines" in item:
        target_name = item["redefines"]
        target = by_name.get(target_name)
        if target is not None:
            # Make sure the target is already sized.
            if "total_bytes" not in target:
                # Size target first (it appeared earlier in source so normally
                # already done; this is a defensive fallback).
                _size_item(target, by_name, 0)
            if "total_bytes_max" in target:
                item["total_bytes_min"] = target.get("total_bytes_min", target["total_bytes_max"])
                item["total_bytes_max"] = target["total_bytes_max"]
                item["total_bytes"] = target["total_bytes_max"]
                item["variable_length"] = True
            else:
                item["total_bytes"] = target["total_bytes"]
            # Continue to also size children (for nested redefines groups).
            # BUT these children do NOT allocate new storage — the item's total
            # comes from the target, not child sum.
            offset = 0
            for ch in children:
                _size_item(ch, by_name, offset)
                offset += int(ch.get("total_bytes", 0))
            # Mark slack 0 for sibling-level accumulation.
            item["slack_bytes_before"] = 0
            return

    # Elementary if it has PIC and no children.
    is_elementary = (not children) and ("pic" in item or item["usage"] in ("POINTER", "COMP-1", "COMP-2"))
    if is_elementary:
        if "pic" in item:
            size, encoding = _parse_pic_bytes(item["pic"], item["usage"])
        else:
            if item["usage"].upper() == "POINTER":
                size, encoding = 8, "pointer"
            elif item["usage"].upper() in ("COMP-1", "COMPUTATIONAL-1"):
                size, encoding = 4, "float"
            elif item["usage"].upper() in ("COMP-2", "COMPUTATIONAL-2"):
                size, encoding = 8, "float"
            else:
                size, encoding = 0, "group"
        # SIGN SEPARATE adds 1 byte on zoned decimal
        if item.get("sign_separate") and encoding == "zoned-decimal":
            size += 1
        item["encoding"] = encoding
        # COMP-5 native flag
        if item["usage"].upper() in ("COMP-5", "COMPUTATIONAL-5"):
            item["comp5_native"] = True  # Note: z/OS native byte order; schema enum has only 'binary'.

        # SYNC: compute slack BEFORE this item so offset is aligned.
        slack = 0
        if item.get("sync"):
            boundary, align_name = _align_of(item["usage"], size)
            if boundary > 1:
                mod = cumulative_offset % boundary
                if mod != 0:
                    slack = boundary - mod
            item["alignment"] = align_name
        item["slack_bytes_before"] = slack

        base = size
    else:
        # Group: size children first, accumulating their SYNC slack.
        offset = 0
        child_sum_min = 0
        child_sum_max = 0
        any_variable = False
        for ch in children:
            _size_item(ch, by_name, offset)
            ch_min = int(ch.get("total_bytes_min", ch.get("total_bytes", 0)))
            ch_max = int(ch.get("total_bytes_max", ch.get("total_bytes", 0)))
            ch_slack = int(ch.get("slack_bytes_before", 0))
            if ch.get("variable_length"):
                any_variable = True
            # REDEFINES children do NOT consume offset (they overlay a sibling).
            if "redefines" in ch:
                continue
            child_sum_min += ch_slack + ch_min
            child_sum_max += ch_slack + ch_max
            offset += ch_slack + ch_max
        item["slack_bytes_before"] = 0  # groups don't SYNC themselves
        base = child_sum_max
        if any_variable or child_sum_min != child_sum_max:
            item["total_bytes_min"] = child_sum_min
            item["total_bytes_max"] = child_sum_max
            item["variable_length"] = True

    # Apply OCCURS.
    if "occurs" in item:
        n = item["occurs"]
        if "total_bytes_min" in item:
            item["total_bytes_min"] *= n
            item["total_bytes_max"] *= n
        base = base * n
    elif "occurs_max" in item:
        # OCCURS DEPENDING ON: element size * [min..max]
        ch_min = int(item.get("total_bytes_min", base))
        ch_max = int(item.get("total_bytes_max", base))
        item["total_bytes_min"] = ch_min * item["occurs_min"]
        item["total_bytes_max"] = ch_max * item["occurs_max"]
        base = item["total_bytes_max"]
        item["variable_length"] = True

    item["total_bytes"] = base


# ---------------------------------------------------------------------------
# Qualified naming
# ---------------------------------------------------------------------------


def _assign_qualified(item: dict, parent_qname: str = "") -> None:
    qname = item["name"] if not parent_qname else f"{parent_qname}.{item['name']}"
    item["qualified_name"] = qname
    for ch in item.get("children", []):
        _assign_qualified(ch, qname)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _flatten_by_name(root: dict, out: dict[str, dict]) -> None:
    out[root["name"]] = root
    for ch in root.get("children", []):
        _flatten_by_name(ch, out)


def _section_of(section_state: str) -> str:
    return {
        "FILE": "file",
        "WORKING-STORAGE": "working_storage",
        "LINKAGE": "linkage",
    }.get(section_state, "unknown")


def run(source_path: Path, out_path: Path, copy_dirs: list[Path]) -> dict:
    lines = _load_source(source_path)
    lines = _expand_copybooks(lines, copy_dirs)
    lines = _join_continuations(lines)
    sentences = _split_sentences(lines)

    # Walk sentences, track section state, and collect DATA DIVISION items.
    section_state = "NONE"  # NONE, FILE, WORKING-STORAGE, LINKAGE
    in_data_div = False
    cur_fd: str | None = None
    # FD-level VARYING metadata: maps fd_name -> {min, max, depending_on}
    # from `RECORD IS VARYING IN SIZE FROM n TO m DEPENDING ON name` clauses.
    fd_varying: dict[str, dict] = {}
    # We keep a per-section flat list preserving source order.
    items_by_section: dict[str, list[dict]] = {
        "file": [],
        "working_storage": [],
        "linkage": [],
    }
    fd_of: dict[int, str] = {}  # id(item) -> fd name for FD-attached roots

    for lineno, sent in sentences:
        up = sent.upper().strip()
        # Division boundaries
        if up.startswith("IDENTIFICATION DIVISION") or up.startswith("ENVIRONMENT DIVISION"):
            in_data_div = False
            section_state = "NONE"
            cur_fd = None
            continue
        if up.startswith("DATA DIVISION"):
            in_data_div = True
            section_state = "NONE"
            cur_fd = None
            continue
        if up.startswith("PROCEDURE DIVISION"):
            in_data_div = False
            section_state = "NONE"
            cur_fd = None
            continue
        if not in_data_div:
            continue
        # Section boundaries inside DATA DIVISION
        if up.startswith("FILE SECTION"):
            section_state = "FILE"; cur_fd = None; continue
        if up.startswith("WORKING-STORAGE SECTION"):
            section_state = "WORKING-STORAGE"; cur_fd = None; continue
        if up.startswith("LINKAGE SECTION"):
            section_state = "LINKAGE"; cur_fd = None; continue
        if up.startswith("LOCAL-STORAGE SECTION"):
            section_state = "WORKING-STORAGE"; cur_fd = None; continue  # fold into WS
        if up.startswith("REPORT SECTION") or up.startswith("SCREEN SECTION") \
                or up.startswith("COMMUNICATION SECTION"):
            section_state = "OTHER"; cur_fd = None; continue
        # FD entry
        mfd = FD_RE.match(sent)
        if mfd and section_state == "FILE":
            cur_fd = mfd.group("name").upper()
            # Parse RECORD IS VARYING IN SIZE FROM n TO m DEPENDING ON <id>
            mv = re.search(
                r"RECORD\s+IS\s+VARYING\s+IN\s+SIZE\s+FROM\s+(\d+)\s+TO\s+(\d+)"
                r"(?:\s+DEPENDING\s+ON\s+([A-Z0-9\-_]+))?",
                sent, re.IGNORECASE,
            )
            if mv:
                fd_varying[cur_fd] = {
                    "min": int(mv.group(1)),
                    "max": int(mv.group(2)),
                    "depending_on": (mv.group(3) or "").upper() or None,
                }
            continue
        # SD (sort) entry — treat like FD
        if up.startswith("SD ") and section_state == "FILE":
            parts = sent.split()
            if len(parts) >= 2:
                cur_fd = parts[1].upper()
            continue

        if section_state not in ("FILE", "WORKING-STORAGE", "LINKAGE"):
            continue

        # Must start with a level number to be a data description entry.
        m = LEVEL_RE.match(sent)
        if not m:
            continue
        level = int(m.group("level"))
        # Filter 88 (condition names) and 66 (RENAMES) — do not create storage.
        if level in (88, 66):
            continue
        # 77 level is elementary at "01 level"; treat as 01 for tree purposes.
        it = _parse_item(sent, lineno)
        if it is None:
            continue
        sect = _section_of(section_state)
        if level == 77:
            it["level"] = 1
            it["level_code"] = 77
        items_by_section[sect].append(it)
        if level == 1 or level == 77:
            if cur_fd:
                it["fd"] = cur_fd

    # Build trees per section.
    trees: dict[str, list[dict]] = {}
    for sect, flat in items_by_section.items():
        trees[sect] = _build_tree(flat)

    # Size everything. Resolve REDEFINES across whole DATA DIVISION (by name).
    by_name: dict[str, dict] = {}
    for sect, roots in trees.items():
        for r in roots:
            _flatten_by_name(r, by_name)
    # Size in source order (roots already in order per section).
    for sect in ("file", "working_storage", "linkage"):
        for r in trees[sect]:
            _size_item(r, by_name, 0)

    # Apply FD-level VARYING (RECORD IS VARYING IN SIZE) to each FD's 01-record.
    # This overrides/augments the 01 record with variable_length and min/max
    # byte counts derived from the FD clause.
    for r in trees["file"]:
        fd_name = r.get("fd")
        if fd_name and fd_name in fd_varying:
            v = fd_varying[fd_name]
            r["variable_length"] = True
            r["total_bytes_min"] = v["min"]
            r["total_bytes_max"] = v["max"]
            r["total_bytes"] = v["max"]
            if v["depending_on"]:
                r["fd_record_depending_on"] = v["depending_on"]
            r["fd_record_format"] = "V"

    # Assign qualified names.
    for sect in ("file", "working_storage", "linkage"):
        for r in trees[sect]:
            _assign_qualified(r)

    # Annotate section on each root.
    def _tag(records: list[dict], section_name: str):
        for r in records:
            r["section"] = section_name
        return records

    out = {
        "program": source_path.stem,
        "source_path": str(source_path),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "sections": {
            "file": _tag(trees["file"], "file"),
            "working_storage": _tag(trees["working_storage"], "working_storage"),
            "linkage": _tag(trees["linkage"], "linkage"),
        },
        "totals": {
            # REDEFINES overlays must not contribute to section totals
            # (they share storage with their target). Enforced at root level
            # here; nested REDEFINES are already excluded inside _size_item.
            "working_storage_bytes": sum(
                int(r.get("total_bytes_max", r.get("total_bytes", 0)))
                for r in trees["working_storage"] if "redefines" not in r
            ),
            "linkage_bytes": sum(
                int(r.get("total_bytes_max", r.get("total_bytes", 0)))
                for r in trees["linkage"] if "redefines" not in r
            ),
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract_byte_layout.py",
        description=(
            "Derive v1.2 byte_layout[] from COBOL DATA DIVISION "
            "(LLM-FREE, deterministic)."
        ),
    )
    parser.add_argument("--source", required=True, help="COBOL source file (read-only)")
    parser.add_argument(
        "--cfg", required=False,
        help="Pass 1 annotations JSON (accepted but not required; RF-07 read-only)",
    )
    parser.add_argument(
        "--copybook-dir", action="append", default=None,
        help="Copybook search root (may be repeated). Default: app/cpy and app/cpy-bms.",
    )
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args(argv)

    source = Path(args.source)
    if not source.exists():
        print(f"ERROR: source not found: {source}", file=sys.stderr)
        return 2

    if args.copybook_dir:
        copy_dirs = [Path(p) for p in args.copybook_dir]
    else:
        repo_root = source.resolve().parent.parent.parent  # app/cbl/X.cbl -> repo
        copy_dirs = [
            repo_root / "app" / "cpy",
            repo_root / "app" / "cpy-bms",
            repo_root / "app" / "cpy-stubs",
        ]

    out = Path(args.out)
    run(source, out, copy_dirs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
