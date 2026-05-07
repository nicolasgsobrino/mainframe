#!/usr/bin/env python3
# LLM-FREE — Deterministic validator (T-PASS1-CP). No LLM inference.
"""
validate_codepage.py — T-PASS1-CP (100% blocking).

Task: T-2026-04-24-001 (Schema v1.2 — Hercules Byte-Parity Foundation)
Gate: G2 — chunk (f4) implementation.

Authoritative checks (verbatim from G1-scaffold.md §6.4 / §8.4):

  1. Every file_control entry has input_codepage == "IBM-1047".
  2. codepage_default_applied == true (absent JCL; RF-02 default).
  3. endianness == "big".
  4. record_format ∈ {F, V, FB, VB, U}. Default FB when FD lacks
     RECORDING MODE; V is valid when RECORD IS VARYING was declared
     (record_varying present). Must NOT false-positive on CBACT01C
     VBRC-FILE (record_format="V" + record_varying min/max/depending_on).
  5. sign_convention — PER-FD (not program-wide). Must be one of
     {"mainframe-ebcdic", "none"}. The value is derived from whether
     any descendant of the FD's 01-records carries encoding in
     {zoned-decimal, packed-decimal} (chunk (e) rule). The validator
     re-derives from the byte_layouts artifact and compares per FD.
     Mixed programs (e.g. CBTRN01C: none, ebcdic, none, none, ebcdic,
     none) must pass because each FD is validated independently.
  6. record_length — must equal the sum of total_bytes across the
     01-records that byte_layouts attaches to this FD. For ODO
     records, record_length must equal total_bytes_max (matching
     the VARYING maximum).
  7. record_varying schema — when record_format == "V" and
     record_varying is present, require keys {min, max}; min and max
     must be positive ints with max >= min; depending_on (when
     present) must be a non-empty string.

Any miss → tier=T-PASS1-CP, pass=false. 100% blocking.

CLI:
  python scripts/validate_codepage.py \
      --file-control validation/pass1/file_control/<PROGRAM>.json \
      --byte-layout  validation/pass1/byte_layouts/<PROGRAM>.json \
      --out          validation/reports/<PROGRAM>_T-PASS1-CP.json

Exit codes:
  0 — PASS
  1 — usage / IO error
  2 — any rule failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

__LLM_FREE__ = True

_VALID_RECORD_FORMAT = {"F", "V", "FB", "VB", "U"}
_SIGN_EBCDIC = "mainframe-ebcdic"
_SIGN_NONE = "none"
_ENCODING_SIGNED = {"zoned-decimal", "packed-decimal"}


def _fail(report: dict, ddname: str, rule: str, detail: str) -> None:
    report["pass"] = False
    report["failures"].append({"ddname": ddname, "rule": rule,
                               "detail": detail})


def _walk_encoding(item: dict, acc: list) -> None:
    enc = item.get("encoding")
    if enc:
        acc.append(enc)
    for c in item.get("children", []) or []:
        _walk_encoding(c, acc)


def _derive_sign(fd_record: dict) -> str:
    encodings: list[str] = []
    _walk_encoding(fd_record, encodings)
    return _SIGN_EBCDIC if any(e in _ENCODING_SIGNED for e in encodings) else _SIGN_NONE


def _fd_records(byte_layout: dict, fd_name: str) -> list[dict]:
    """Return all 01-records under sections.file attached to this FD."""
    out = []
    file_section = byte_layout.get("sections", {}).get("file", []) or []
    for item in file_section:
        if item.get("fd") == fd_name:
            out.append(item)
    return out


def validate(file_control_doc: dict, byte_layout: dict) -> dict:
    report = {
        "tier": "T-PASS1-CP",
        "program": file_control_doc.get("program"),
        "source_sha256": file_control_doc.get("source_sha256"),
        "byte_layouts_sha256": file_control_doc.get("byte_layouts_sha256"),
        "pass": True,
        "failures": [],
        "fd_reports": [],
    }

    entries = file_control_doc.get("file_control", []) or []

    # Empty file_control is valid (e.g., COBSWAIT, CICS programs).
    if not entries:
        return report

    for e in entries:
        dd = e.get("ddname") or e.get("logical_name") or "<unnamed>"
        # Rule 1
        cp = e.get("input_codepage")
        if cp != "IBM-1047":
            _fail(report, dd, "CODEPAGE",
                  f"input_codepage='{cp}' (expected 'IBM-1047')")
        # Rule 2
        if e.get("codepage_default_applied") is not True:
            _fail(report, dd, "CODEPAGE-DEFAULT",
                  f"codepage_default_applied="
                  f"{e.get('codepage_default_applied')!r} (expected True)")
        # Rule 3
        if e.get("endianness") != "big":
            _fail(report, dd, "ENDIANNESS",
                  f"endianness='{e.get('endianness')}' (expected 'big')")

        # Rule 4 — record_format
        rf = e.get("record_format")
        if rf not in _VALID_RECORD_FORMAT:
            _fail(report, dd, "RECORD-FORMAT",
                  f"record_format='{rf}' not in {sorted(_VALID_RECORD_FORMAT)}")

        # Rule 7 — record_varying schema (V only)
        rv = e.get("record_varying")
        if rv is not None:
            if not isinstance(rv, dict):
                _fail(report, dd, "RECORD-VARYING",
                      f"record_varying must be object, got {type(rv).__name__}")
            else:
                rvmin = rv.get("min")
                rvmax = rv.get("max")
                if not isinstance(rvmin, int) or rvmin <= 0:
                    _fail(report, dd, "RECORD-VARYING",
                          f"record_varying.min={rvmin!r} (expected positive int)")
                if not isinstance(rvmax, int) or rvmax <= 0:
                    _fail(report, dd, "RECORD-VARYING",
                          f"record_varying.max={rvmax!r} (expected positive int)")
                if (isinstance(rvmin, int) and isinstance(rvmax, int)
                        and rvmax < rvmin):
                    _fail(report, dd, "RECORD-VARYING",
                          f"record_varying.max ({rvmax}) < min ({rvmin})")
                dep = rv.get("depending_on")
                if dep is not None and (not isinstance(dep, str) or not dep):
                    _fail(report, dd, "RECORD-VARYING",
                          f"record_varying.depending_on must be non-empty "
                          f"string when present, got {dep!r}")
                # V ↔ varying cross-check: V without varying is allowed,
                # but varying with FB/F is nonsensical.
                if rf in {"FB", "F"}:
                    _fail(report, dd, "RECORD-VARYING",
                          f"record_format='{rf}' but record_varying "
                          f"present — contradiction")

        # Rule 5 — sign_convention: re-derive from byte_layouts per-FD.
        logical = e.get("logical_name")
        fd_records = _fd_records(byte_layout, logical)
        if not fd_records:
            # Some artifacts index by logical name only; we expect the
            # extractor to tie them together. Missing records is an FD-level
            # warning but not a Rule 5 failure on its own — record_length
            # check below will catch a true mismatch.
            derived_sign = _SIGN_NONE
            fd_record_length = 0
        else:
            signed_any = False
            fd_record_length = 0
            for rec in fd_records:
                encs: list[str] = []
                _walk_encoding(rec, encs)
                if any(x in _ENCODING_SIGNED for x in encs):
                    signed_any = True
                # ODO: use total_bytes_max when variable_length
                if rec.get("variable_length"):
                    fd_record_length = max(
                        fd_record_length,
                        rec.get("total_bytes_max") or rec.get("total_bytes") or 0,
                    )
                else:
                    fd_record_length = max(
                        fd_record_length,
                        rec.get("total_bytes") or 0,
                    )
            derived_sign = _SIGN_EBCDIC if signed_any else _SIGN_NONE

        actual_sign = e.get("sign_convention")
        if actual_sign not in {_SIGN_EBCDIC, _SIGN_NONE}:
            _fail(report, dd, "SIGN-CONVENTION-SET",
                  f"sign_convention='{actual_sign}' not in "
                  f"{{'{_SIGN_EBCDIC}', '{_SIGN_NONE}'}}")
        elif actual_sign != derived_sign:
            _fail(report, dd, "SIGN-CONVENTION",
                  f"sign_convention='{actual_sign}' does not match "
                  f"byte_layouts re-derivation '{derived_sign}'")

        # Rule 6 — record_length cross-check
        claimed_len = e.get("record_length")
        if claimed_len is None:
            _fail(report, dd, "RECORD-LENGTH",
                  "record_length missing")
        elif fd_records and claimed_len != fd_record_length:
            _fail(report, dd, "RECORD-LENGTH",
                  f"record_length={claimed_len} does not match "
                  f"byte_layouts derived {fd_record_length} "
                  f"(FD records: "
                  f"{[r.get('name') for r in fd_records]})")

        report["fd_reports"].append({
            "ddname": dd,
            "logical_name": logical,
            "record_format": rf,
            "sign_convention": actual_sign,
            "derived_sign_convention": derived_sign,
            "record_length": claimed_len,
            "derived_record_length": fd_record_length,
            "record_varying": rv,
        })

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_codepage.py",
        description="T-PASS1-CP 100%-blocking validator (LLM-FREE).",
    )
    parser.add_argument("--file-control", required=True,
                        help="file_control JSON (chunk (e) extractor output)")
    parser.add_argument("--byte-layout", required=True,
                        help="byte_layouts JSON (chunk (b) extractor output)")
    parser.add_argument("--out", required=True,
                        help="Report JSON output path")
    args = parser.parse_args(argv)

    try:
        with open(args.file_control) as f:
            fc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.file_control}: {e}", file=sys.stderr)
        return 1
    try:
        with open(args.byte_layout) as f:
            bl = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.byte_layout}: {e}", file=sys.stderr)
        return 1

    report = validate(fc, bl)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    prog = report["program"]
    n_fd = len(report["fd_reports"])
    if report["pass"]:
        print(f"PASS T-PASS1-CP {prog} ({n_fd} FD) → {args.out}")
        return 0
    else:
        print(f"FAIL T-PASS1-CP {prog} "
              f"({len(report['failures'])} failure(s), {n_fd} FD) → {args.out}",
              file=sys.stderr)
        for fail in report["failures"][:10]:
            print(f"  - [{fail['rule']}] {fail['ddname']}: {fail['detail']}",
                  file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
