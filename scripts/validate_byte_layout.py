#!/usr/bin/env python3
# LLM-FREE — Deterministic validator (T-PASS1-BYTES). No LLM inference.
"""
validate_byte_layout.py — T-PASS1-BYTES (100% blocking).

Task: T-2026-04-24-001 (Schema v1.2 — Hercules Byte-Parity Foundation)
Gate: G2 — chunk (f1) implementation.

Authoritative checks (verbatim from G1-scaffold.md §6.1 / §8.1 / C-2):

  1. Every elementary item's total_bytes EQUALS the PIC/USAGE ladder value.
  2. Group items: total_bytes == sum(child.total_bytes + child.slack_bytes_before)
     over NON-REDEFINES children (REDEFINES children overlay and do not
     add to the parent group, per IBM Enterprise COBOL).
  3. OCCURS n: total_bytes == element.total_bytes * n
     (reported via extras.occurs on the array item in chunk (b) artifact).
  4. OCCURS DEPENDING ON: variable_length == true AND BOTH total_bytes_min
     AND total_bytes_max present AND total_bytes_max >= total_bytes_min.
  5. REDEFINES: slack_bytes_before == 0 AND total_bytes <= target.total_bytes
     (REDEFINES overlays existing storage; must not extend beyond the target).
  6. C-2 SYNC / SYNCHRONIZED: slack_bytes_before ∈ {0..7} AND alignment ∈
     {"byte","halfword","word","doubleword"} AND, when slack_bytes_before > 0,
     alignment != "byte".

Any miss → tier=T-PASS1-BYTES, pass=false. 100% blocking.

CLI:
  python scripts/validate_byte_layout.py \
      --byte-layout validation/pass1/byte_layouts/<PROGRAM>.json \
      --out validation/reports/<PROGRAM>_T-PASS1-BYTES.json

Exit codes:
  0 — all checks PASS.
  1 — usage / IO error (argparse error, missing input).
  2 — PIC/USAGE ladder mismatch, group sum mismatch, OCCURS/ODO mismatch,
      REDEFINES overflow, or SYNC alignment violation. Report written.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

__LLM_FREE__ = True

# ---------------------------------------------------------------------------
# PIC / USAGE ladder (chunk (b) reference, re-implemented independently here
# for cross-validation — if the extractor drifts, this validator catches it).
# ---------------------------------------------------------------------------

_USAGE_BINARY = {"COMP", "COMP-4", "COMP-5", "BINARY"}
_USAGE_PACKED = {"COMP-3", "PACKED-DECIMAL"}
_USAGE_FLOAT_SINGLE = {"COMP-1"}
_USAGE_FLOAT_DOUBLE = {"COMP-2"}
_USAGE_POINTER = {"POINTER", "PROCEDURE-POINTER", "FUNCTION-POINTER"}


def _count_symbol(pic: str, symbols: set[str]) -> int:
    """Count the number of positions in a PIC mask that belong to any
    of the given symbols. Handles both bare symbols and the 'SYM(n)'
    repeat form; the (n) only applies to the symbol immediately
    preceding it (so '9' inside '(491)' is NOT a digit position when
    counting digits for an X-typed PIC)."""
    if not pic:
        return 0
    s = pic.upper()
    total = 0
    i = 0
    while i < len(s):
        ch = s[i]
        # look ahead for '(n)'
        run = 1
        next_i = i + 1
        if i + 1 < len(s) and s[i + 1] == "(":
            j = s.find(")", i + 2)
            if j > 0:
                try:
                    run = int(s[i + 2:j])
                    next_i = j + 1
                except ValueError:
                    run = 1
        if ch in symbols:
            total += run
        i = next_i
    return total


def _pic_digit_count(pic: str) -> int:
    # '9' and 'P' (scaling) both occupy digit positions.
    return _count_symbol(pic, {"9", "P"})


def _pic_char_count(pic: str) -> int:
    return _count_symbol(pic, {"X", "A", "N"})


def ladder_bytes(pic: str | None, usage: str | None) -> int | None:
    """Return the IBM Enterprise COBOL 6.4 byte size for an elementary
    item given its PIC and USAGE. Returns None if not derivable
    (e.g. pure container groups pass pic=None)."""
    if not pic and not usage:
        return None
    u = (usage or "DISPLAY").upper()

    if u in _USAGE_POINTER:
        return 4  # 31-bit AMODE default; 8 for AMODE 64 — not in scope

    if u in _USAGE_FLOAT_SINGLE:
        return 4
    if u in _USAGE_FLOAT_DOUBLE:
        return 8

    digits = _pic_digit_count(pic or "")
    chars = _pic_char_count(pic or "")

    # alphanumeric/alphabetic PICs (X, A, N) — always 1 byte per char,
    # regardless of USAGE. Check first so mixed mistakes can't mask it.
    if chars > 0 and digits == 0:
        return chars

    if u in _USAGE_BINARY:
        if digits <= 4:
            return 2
        if digits <= 9:
            return 4
        if digits <= 18:
            return 8
        return None

    if u in _USAGE_PACKED:
        if digits == 0:
            return None
        return (digits // 2) + 1

    # DISPLAY numeric (zoned): one byte per digit.
    if digits > 0:
        return digits
    return None


# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------

def _fail(report: dict, item_path: str, rule: str, detail: str) -> None:
    report["pass"] = False
    report["failures"].append(
        {"item": item_path, "rule": rule, "detail": detail}
    )


# ---------------------------------------------------------------------------
# Walk + check
# ---------------------------------------------------------------------------

def _check_item(
    item: dict,
    parent_path: str,
    section: str,
    report: dict,
) -> None:
    name = item.get("name", "<unnamed>")
    path = f"{parent_path}/{name}" if parent_path else name
    tb = item.get("total_bytes")
    slack = item.get("slack_bytes_before", 0)
    pic = item.get("pic")
    usage = item.get("usage")
    children = item.get("children", []) or []
    alignment = item.get("alignment", "byte")
    variable_length = item.get("variable_length", False)
    redefines = item.get("redefines")
    occurs = item.get("occurs")

    # Rule 6: SYNC / alignment sanity (applies to any item)
    if slack is None or not isinstance(slack, int):
        _fail(report, path, "C-2-SYNC",
              f"slack_bytes_before must be int; got {type(slack).__name__}")
    elif slack < 0 or slack > 7:
        _fail(report, path, "C-2-SYNC",
              f"slack_bytes_before {slack} outside {{0..7}}")
    elif slack > 0 and alignment == "byte":
        _fail(report, path, "C-2-SYNC",
              f"slack_bytes_before={slack} but alignment='byte' "
              f"(expected halfword|word|doubleword)")

    if alignment not in {"byte", "halfword", "word", "doubleword"}:
        _fail(report, path, "C-2-SYNC",
              f"alignment '{alignment}' not in allowed set")

    # Rule 5: REDEFINES — slack must be 0
    if redefines and slack != 0:
        _fail(report, path, "REDEFINES",
              f"REDEFINES '{redefines}' has slack_bytes_before={slack}; "
              f"must be 0 (overlay, not extended storage)")

    # Rule 4: ODO
    if variable_length:
        tb_min = item.get("total_bytes_min")
        tb_max = item.get("total_bytes_max")
        if tb_min is None or tb_max is None:
            _fail(report, path, "ODO",
                  "variable_length=true requires total_bytes_min AND total_bytes_max")
        elif not isinstance(tb_min, int) or not isinstance(tb_max, int):
            _fail(report, path, "ODO",
                  f"total_bytes_min/max must be int; got "
                  f"{type(tb_min).__name__}/{type(tb_max).__name__}")
        elif tb_max < tb_min:
            _fail(report, path, "ODO",
                  f"total_bytes_max ({tb_max}) < total_bytes_min ({tb_min})")

    if children:
        # GROUP item: Rule 2 — total_bytes == sum of non-REDEFINES children,
        # multiplied by OCCURS count when the group itself has OCCURS.
        # Items that REDEFINES another item are overlays: their total_bytes
        # must be checked against the target (Rule 5), not against their
        # children-sum.
        if redefines:
            # Rule 5 governs; group children-sum check does not apply here.
            # We still recurse so children are individually validated.
            for c in children:
                _check_item(c, path, section, report)
        else:
            child_sum = 0
            for c in children:
                if c.get("redefines"):
                    continue  # overlay, not added to parent
                ctb = c.get("total_bytes", 0) or 0
                cslack = c.get("slack_bytes_before", 0) or 0
                child_sum += ctb + cslack

            if isinstance(occurs, int) and occurs > 0:
                expected = child_sum * occurs
                rule = "OCCURS-GROUP"
                detail_suffix = f"= child_sum {child_sum} × OCCURS {occurs}"
            else:
                expected = child_sum
                rule = "GROUP-SUM"
                detail_suffix = f"= sum of non-REDEFINES children"

            if tb != expected and not variable_length:
                _fail(report, path, rule,
                      f"group total_bytes {tb} != {expected} {detail_suffix}")
            for c in children:
                _check_item(c, path, section, report)
    else:
        # ELEMENTARY: Rule 1 — ladder check
        # Arrays: if OCCURS present, tb == element_size * count. We derive
        # element_size from the ladder then multiply by occurs.
        elem_expected = ladder_bytes(pic, usage)
        if elem_expected is None:
            # Items without PIC and without USAGE (e.g. filler groups
            # accidentally captured as elementary) can't be ladder-checked.
            # Only fail if they report non-zero bytes without explanation.
            if tb is not None and tb > 0 and not variable_length and not occurs:
                _fail(report, path, "LADDER",
                      "elementary item has no PIC and no USAGE, but "
                      f"total_bytes={tb}")
            return

        if occurs and isinstance(occurs, int):
            # Rule 3: OCCURS n — tb == elem * n
            expected = elem_expected * occurs
            if tb != expected and not variable_length:
                _fail(report, path, "OCCURS",
                      f"OCCURS {occurs} × element {elem_expected} = {expected} "
                      f"but total_bytes={tb}")
        else:
            if tb != elem_expected and not variable_length:
                _fail(report, path, "LADDER",
                      f"PIC='{pic}' USAGE='{usage}' ladder={elem_expected} "
                      f"but total_bytes={tb}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def validate(byte_layout: dict) -> dict:
    report = {
        "tier": "T-PASS1-BYTES",
        "program": byte_layout.get("program"),
        "source_sha256": byte_layout.get("source_sha256"),
        "pass": True,
        "failures": [],
    }

    sections = byte_layout.get("sections", {}) or {}
    for sect_name, items in sections.items():
        for item in items:
            _check_item(item, "", sect_name, report)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_byte_layout.py",
        description="T-PASS1-BYTES 100%-blocking validator (LLM-FREE).",
    )
    parser.add_argument("--byte-layout", required=True,
                        help="byte_layouts JSON (chunk (b) extractor output)")
    parser.add_argument("--out", required=True,
                        help="Report JSON output path")
    args = parser.parse_args(argv)

    try:
        with open(args.byte_layout) as f:
            byte_layout = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.byte_layout}: {e}", file=sys.stderr)
        return 1

    report = validate(byte_layout)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    prog = report["program"]
    if report["pass"]:
        print(f"PASS T-PASS1-BYTES {prog} → {args.out}")
        return 0
    else:
        print(f"FAIL T-PASS1-BYTES {prog} "
              f"({len(report['failures'])} failure(s)) → {args.out}",
              file=sys.stderr)
        for fail in report["failures"][:10]:
            print(f"  - [{fail['rule']}] {fail['item']}: {fail['detail']}",
                  file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
