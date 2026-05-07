#!/usr/bin/env python3
# LLM-FREE — Deterministic SELECT/FD + record-length derivation. No LLM inference.
"""
extract_file_control.py — Derive v1.2 file_control[] from COBOL ENVIRONMENT
and DATA DIVISION FILE SECTION.

Task: T-2026-04-24-001 (Schema v1.2 — Hercules Byte-Parity Foundation)
Chunk: (e)

Authoritative rules (G1-scaffold.md §6.4 / §8.4):

    For each SELECT <logical-file> ASSIGN TO <ddname> clause in the
    ENVIRONMENT DIVISION, and its matching FD <logical-file> entry in
    DATA DIVISION FILE SECTION, emit one file_control record:

      logical_name       : <SELECT logical-file-name>
      ddname             : <SELECT ASSIGN TO ddname>
      organization       : SEQUENTIAL|INDEXED|RELATIVE|LINE-SEQUENTIAL
                           (from SELECT ORGANIZATION IS ...; default SEQUENTIAL)
      access_mode        : SEQUENTIAL|RANDOM|DYNAMIC
                           (from SELECT ACCESS MODE IS ...; default SEQUENTIAL)
      record_key         : <SELECT RECORD KEY IS ...> or null
      alternate_keys     : [SELECT ALTERNATE RECORD KEY IS ...]  (list)
      file_status        : <SELECT FILE STATUS IS ...> or null
      record_format      : derived from FD RECORDING MODE IS F|V|FB|VB|U
                           (default FB if absent)
      record_length      : sum of byte_layout.total_bytes over FD 01-records
      input_codepage     : "IBM-1047"      (hardcoded default, §8.4 rule)
      codepage_default_applied: true       (flag: no CODEPAGE stmt in source)
      sign_convention    : "mainframe-ebcdic" if any numeric DISPLAY
                           (encoding=zoned-decimal) OR packed-decimal item
                           is declared under this FD; else "none"
      endianness         : "big"           (z/OS mainframe constant)

Inputs:
  --source       app/cbl/<PROGRAM>.cbl                     (read-only, RF-06)
  --byte-layout  validation/pass1/byte_layouts/<PROGRAM>.json  (read-only)
  --out          validation/pass1/file_control/<PROGRAM>.json

Output: JSON of the form

    {
      "program": str,
      "source_path": str,
      "source_sha256": str,
      "byte_layouts_path": str,
      "byte_layouts_sha256": str,
      "file_control": [
        { logical_name, ddname, organization, access_mode,
          record_key, alternate_keys, file_status,
          record_format, record_length,
          input_codepage, codepage_default_applied,
          sign_convention, endianness },
        ...
      ]
    }

RF-07 STANDALONE: pass1_annotate.py is NOT opened, read, or modified.
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
# Source preprocessing
# ---------------------------------------------------------------------------

def preprocess_source(raw_text: str):
    """Yield (lineno, text) tuples with COBOL columns 7–72 normalised.

    - Col 1-6 sequence area: discarded.
    - Col 7 indicator: '*' or '/' = comment (skip), 'D' = debug (skip),
      '-' = continuation (handled by callers where relevant), else blank.
    - Col 8-72: kept as source area; trailing whitespace stripped.
    - Col 73+: identification area: discarded.

    `lineno` is 1-based.
    """
    out = []
    for i, line in enumerate(raw_text.splitlines(), start=1):
        # Pad short lines to at least 72 columns (avoids index errors)
        padded = line.ljust(72)
        indicator = padded[6:7] if len(line) > 6 else " "
        if indicator in ("*", "/", "D", "d"):
            continue
        text = padded[6:72].rstrip()  # keep indicator at start so we can see '-'
        out.append((i, text))
    return out


def flatten_area_a(lines):
    """Return a single string of the program area joined, preserving newlines
    so we can still compute line numbers from offsets. Returns (joined, offsets)
    where offsets[line_index] = starting char offset in joined string.
    """
    joined_parts = []
    offsets = []
    char = 0
    for lineno, text in lines:
        offsets.append((lineno, char))
        joined_parts.append(text + "\n")
        char += len(text) + 1
    return "".join(joined_parts), offsets


def lineno_at(offsets, pos: int) -> int:
    """Given (lineno, char_offset) pairs, return the source lineno for a
    character position in the flattened text."""
    # Linear search is fine for our file sizes
    last = offsets[0][0] if offsets else 0
    for ln, off in offsets:
        if off > pos:
            break
        last = ln
    return last


# ---------------------------------------------------------------------------
# SELECT parser
# ---------------------------------------------------------------------------

SELECT_RE = re.compile(r"\bSELECT\b", re.IGNORECASE)


def locate_file_control(joined: str):
    """Return (start, end) char offsets for FILE-CONTROL ... (before DATA
    DIVISION or next DIVISION). If FILE-CONTROL absent, return None."""
    m_fc = re.search(r"\bFILE\s*-\s*CONTROL\s*\.", joined, re.IGNORECASE)
    if not m_fc:
        return None
    start = m_fc.end()
    # End = DATA DIVISION, or I-O-CONTROL, or next DIVISION
    end_candidates = []
    for pat in (r"\bDATA\s+DIVISION\s*\.", r"\bI-O-CONTROL\s*\.",
                r"\bPROCEDURE\s+DIVISION\s*\."):
        m = re.search(pat, joined[start:], re.IGNORECASE)
        if m:
            end_candidates.append(start + m.start())
    end = min(end_candidates) if end_candidates else len(joined)
    return (start, end)


def parse_selects(joined: str, offsets):
    fc = locate_file_control(joined)
    if not fc:
        return []
    block = joined[fc[0]:fc[1]]
    base = fc[0]

    # Split on period (SELECTs end with '.'). Periods inside literals could
    # be tricky but SELECT clauses don't include literals.
    selects = []
    # Find each SELECT ... . statement
    stmt_positions = []
    for m in SELECT_RE.finditer(block):
        stmt_positions.append(m.start())
    stmt_positions.append(len(block))  # sentinel

    for i in range(len(stmt_positions) - 1):
        s = stmt_positions[i]
        e = stmt_positions[i + 1]
        segment = block[s:e]
        # Trim at first period-at-end-of-clause (period followed by whitespace or end)
        end_match = re.search(r"\.(?=\s|$)", segment)
        if end_match:
            segment = segment[:end_match.start()]
        abs_start = base + s

        # Now parse this SELECT segment
        # Collapse whitespace
        flat = re.sub(r"\s+", " ", segment).strip()

        # logical_name: first token after SELECT
        m_name = re.match(r"SELECT\s+([A-Za-z0-9\-]+)", flat, re.IGNORECASE)
        if not m_name:
            continue
        logical_name = m_name.group(1).upper()

        m_assign = re.search(r"\bASSIGN\s+TO\s+([A-Za-z0-9\-]+)", flat, re.IGNORECASE)
        ddname = m_assign.group(1).upper() if m_assign else None

        m_org = re.search(
            r"\bORGANIZATION\s+(?:IS\s+)?(SEQUENTIAL|INDEXED|RELATIVE|LINE\s+SEQUENTIAL|LINE-SEQUENTIAL)",
            flat, re.IGNORECASE,
        )
        if m_org:
            org = m_org.group(1).upper().replace(" ", "-")
        else:
            org = "SEQUENTIAL"  # default per §8.4

        m_access = re.search(
            r"\bACCESS\s+(?:MODE\s+)?(?:IS\s+)?(SEQUENTIAL|RANDOM|DYNAMIC)",
            flat, re.IGNORECASE,
        )
        access_mode = m_access.group(1).upper() if m_access else "SEQUENTIAL"

        m_key = re.search(
            r"\bRECORD\s+KEY\s+(?:IS\s+)?([A-Za-z0-9\-]+)",
            flat, re.IGNORECASE,
        )
        record_key = m_key.group(1).upper() if m_key else None

        alternate_keys = [
            m.group(1).upper()
            for m in re.finditer(
                r"\bALTERNATE\s+RECORD\s+KEY\s+(?:IS\s+)?([A-Za-z0-9\-]+)",
                flat, re.IGNORECASE,
            )
        ]

        m_fs = re.search(
            r"\bFILE\s+STATUS\s+(?:IS\s+)?([A-Za-z0-9\-]+)",
            flat, re.IGNORECASE,
        )
        file_status = m_fs.group(1).upper() if m_fs else None

        selects.append({
            "logical_name": logical_name,
            "ddname": ddname,
            "organization": org,
            "access_mode": access_mode,
            "record_key": record_key,
            "alternate_keys": alternate_keys,
            "file_status": file_status,
            "line": lineno_at(offsets, abs_start),
        })
    return selects


# ---------------------------------------------------------------------------
# FD parser
# ---------------------------------------------------------------------------

def locate_file_section(joined: str):
    m = re.search(r"\bFILE\s+SECTION\s*\.", joined, re.IGNORECASE)
    if not m:
        return None
    start = m.end()
    # End at next SECTION (WORKING-STORAGE / LINKAGE / LOCAL-STORAGE) or
    # PROCEDURE DIVISION
    end_candidates = []
    for pat in (r"\bWORKING-STORAGE\s+SECTION\s*\.",
                r"\bLINKAGE\s+SECTION\s*\.",
                r"\bLOCAL-STORAGE\s+SECTION\s*\.",
                r"\bPROCEDURE\s+DIVISION\s*\."):
        m2 = re.search(pat, joined[start:], re.IGNORECASE)
        if m2:
            end_candidates.append(start + m2.start())
    end = min(end_candidates) if end_candidates else len(joined)
    return (start, end)


def parse_fds(joined: str, offsets):
    """Return list of dicts: {name, line, recording_mode, record_varying,
    header_end_line (first 01 or next FD line)}."""
    fs = locate_file_section(joined)
    if not fs:
        return []
    block = joined[fs[0]:fs[1]]
    base = fs[0]

    # Find FD entries: "FD  <name>" at start of program area
    # Note: FD may also appear as "SD" (SORT) — treat the same? Spec only
    # mentions FD. We handle only FD.
    # Pattern: word boundary FD followed by whitespace then identifier.
    fd_matches = list(re.finditer(
        r"(?m)^\s*FD\s+([A-Za-z0-9\-]+)",
        block,
    ))

    fds = []
    for i, m in enumerate(fd_matches):
        abs_start = base + m.start()
        name = m.group(1).upper()
        # Segment = from this FD until next FD or end of FILE SECTION, limited
        # by the first 01-level (header info lives between "FD name" and the
        # first 01 record) — but RECORDING MODE can be on multiple lines
        # before the 01 record.
        seg_start = m.end()
        seg_end = fd_matches[i + 1].start() if i + 1 < len(fd_matches) else len(block)
        # The FD "header" ends at the first 01 (or at the terminating period)
        m_01 = re.search(r"(?m)^\s*01\s+", block[seg_start:seg_end])
        header_end = seg_start + m_01.start() if m_01 else seg_end
        header = block[seg_start:header_end]
        header_flat = re.sub(r"\s+", " ", header).strip()

        # Parse RECORDING MODE IS F|V|FB|VB|U
        m_rec = re.search(
            r"\bRECORDING\s+MODE\s+(?:IS\s+)?(FB|VB|F|V|U)\b",
            header_flat, re.IGNORECASE,
        )
        recording_mode = m_rec.group(1).upper() if m_rec else None

        # VARYING IN SIZE FROM <n> TO <m> [DEPENDING ON <id>]
        m_var = re.search(
            r"\bRECORD\s+IS\s+VARYING\s+IN\s+SIZE\s+FROM\s+(\d+)\s+TO\s+(\d+)"
            r"(?:\s+DEPENDING(?:\s+ON)?\s+([A-Z0-9][A-Z0-9-]*))?",
            header_flat, re.IGNORECASE,
        )
        record_varying = None
        if m_var:
            record_varying = {
                "min": int(m_var.group(1)),
                "max": int(m_var.group(2)),
            }
            if m_var.group(3):
                record_varying["depending_on"] = m_var.group(3).upper()

        fds.append({
            "name": name,
            "line": lineno_at(offsets, abs_start),
            "recording_mode": recording_mode,
            "record_varying": record_varying,
        })
    return fds


# ---------------------------------------------------------------------------
# byte_layouts integration
# ---------------------------------------------------------------------------

def collect_file_records(byte_layout: dict):
    """Return list of 01-level records (with full children) from the file
    section, annotated with their source line."""
    records = []
    for item in byte_layout.get("sections", {}).get("file", []):
        records.append(item)
    return records


def has_ebcdic_sign(record: dict) -> bool:
    """Return True if the record (or any descendant) carries a numeric
    DISPLAY (zoned-decimal) or packed-decimal encoding, which requires a
    mainframe EBCDIC sign convention."""
    enc = (record.get("encoding") or "").lower()
    if enc in ("zoned-decimal", "packed-decimal"):
        return True
    for ch in record.get("children") or []:
        if has_ebcdic_sign(ch):
            return True
    return False


def assign_records_to_fds(fds: list, file_records: list):
    """Assign each 01-level record to the FD whose source line immediately
    precedes it. Returns dict fd_name -> list-of-records."""
    assignment = {fd["name"]: [] for fd in fds}
    if not fds:
        return assignment
    sorted_fds = sorted(fds, key=lambda f: f["line"])
    for rec in file_records:
        rec_line = rec.get("line", 0)
        # Find the FD whose line is <= rec_line and closest to it
        chosen = None
        for fd in sorted_fds:
            if fd["line"] <= rec_line:
                chosen = fd
            else:
                break
        if chosen is not None:
            assignment[chosen["name"]].append(rec)
    return assignment


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build_file_control(selects: list, fds: list, byte_layout: dict):
    file_records = collect_file_records(byte_layout)
    fd_by_name = {fd["name"]: fd for fd in fds}
    fd_records = assign_records_to_fds(fds, file_records)

    out = []
    for sel in selects:
        lname = sel["logical_name"]
        fd = fd_by_name.get(lname)
        recs = fd_records.get(lname, []) if fd else []

        record_length = sum(r.get("total_bytes", 0) or 0 for r in recs)

        # record_format: recording_mode if set, else VARYING → "V"/"VB",
        # else default FB
        rec_mode = fd["recording_mode"] if fd else None
        record_format = rec_mode or "FB"
        if fd and fd.get("record_varying") and not rec_mode:
            # VARYING with no explicit RECORDING MODE → V (variable)
            record_format = "V"

        # sign_convention
        sign = "none"
        if any(has_ebcdic_sign(r) for r in recs):
            sign = "mainframe-ebcdic"

        entry = {
            "logical_name": lname,
            "ddname": sel["ddname"],
            "organization": sel["organization"],
            "access_mode": sel["access_mode"],
            "record_key": sel["record_key"],
            "alternate_keys": sel["alternate_keys"],
            "file_status": sel["file_status"],
            "record_format": record_format,
            "record_length": record_length,
            "input_codepage": "IBM-1047",
            "codepage_default_applied": True,
            "sign_convention": sign,
            "endianness": "big",
        }
        if fd and fd.get("record_varying"):
            entry["record_varying"] = fd["record_varying"]
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(source_path: Path, byte_layouts_path: Path) -> dict:
    source_text = source_path.read_text()
    source_sha = sha256_of(source_path)
    bl_sha = sha256_of(byte_layouts_path)
    byte_layout = json.loads(byte_layouts_path.read_text())

    lines = preprocess_source(source_text)
    joined, offsets = flatten_area_a(lines)

    selects = parse_selects(joined, offsets)
    fds = parse_fds(joined, offsets)

    file_control = build_file_control(selects, fds, byte_layout)

    return {
        "program": byte_layout.get("program") or source_path.stem,
        "source_path": str(source_path),
        "source_sha256": source_sha,
        "byte_layouts_path": str(byte_layouts_path),
        "byte_layouts_sha256": bl_sha,
        "file_control": file_control,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract_file_control.py",
        description="Derive v1.2 file_control[] from SELECT+FD (LLM-FREE).",
    )
    parser.add_argument("--source", required=True,
                        help="COBOL source file (read-only)")
    parser.add_argument("--byte-layout", "--byte-layouts", required=True,
                        dest="byte_layout",
                        help="byte_layout JSON (read-only)")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    bl_path = Path(args.byte_layout)
    out_path = Path(args.out)
    for p, label in ((source_path, "source"), (bl_path, "byte-layout")):
        if not p.is_file():
            print(f"ERROR: {label} path not found: {p}", file=sys.stderr)
            return 2

    out = extract(source_path, bl_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {out_path} ({len(out['file_control'])} file_control entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
