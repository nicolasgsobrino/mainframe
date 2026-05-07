#!/usr/bin/env python3
# LLM-FREE — Deterministic validator (T-PASS1-FT). No LLM inference.
"""
validate_fallthrough.py — T-PASS1-FT (100% blocking).

Task: T-2026-04-24-001 (Schema v1.2 — Hercules Byte-Parity Foundation)
Gate: G2 — chunk (f2) implementation.

Authoritative checks (verbatim from G1-scaffold.md §6.2 / §8.2 / C-5):

  1. Every paragraph in the artifact has exactly one entry with the
     required keys: paragraph, first_line, last_line, terminator,
     falls_through_to.
  2. terminator ∈ {goto, stop-run, goback, explicit-exit, cics-return,
                   cics-xctl, implicit, implicit-end-of-program}.
  3. terminator == "implicit" ↔ falls_through_to is the NAME of the
     next paragraph in source order; otherwise falls_through_to MUST
     be null.
  4. The last paragraph in source order MUST NOT have terminator
     "implicit" (no successor to fall to).
  5. C-5 source-order guard: for every consecutive pair (n, n+1):
        first_line[n+1] > last_line[n]
     (strict non-overlap + strict increasing order).
  6. Artifact self-reports c5_assertion == "PASS" and
     c5_violations == [] — if the extractor reported a violation, the
     validator echoes it.

Any miss → tier=T-PASS1-FT, pass=false. 100% blocking.

CLI:
  python scripts/validate_fallthrough.py \
      --fallthrough validation/pass1/fallthrough/<PROGRAM>.json \
      --out validation/reports/<PROGRAM>_T-PASS1-FT.json

Exit codes:
  0 — PASS
  1 — usage / IO error
  2 — any rule failure; report written with failures[].
"""
from __future__ import annotations

import argparse
import json
import os
import sys

__LLM_FREE__ = True

_VALID_TERMINATORS = {
    "goto",
    "stop-run",
    "goback",
    "explicit-exit",
    "cics-return",
    "cics-xctl",
    "implicit",
    "implicit-end-of-program",
}

_REQUIRED_KEYS = {"paragraph", "first_line", "last_line", "terminator",
                  "falls_through_to"}


def _fail(report: dict, para: str, rule: str, detail: str) -> None:
    report["pass"] = False
    report["failures"].append({"paragraph": para, "rule": rule,
                               "detail": detail})


def validate(artifact: dict) -> dict:
    report = {
        "tier": "T-PASS1-FT",
        "program": artifact.get("program"),
        "source_sha256": artifact.get("source_sha256"),
        "cfg_sha256": artifact.get("cfg_sha256"),
        "pass": True,
        "failures": [],
    }

    paragraphs = artifact.get("paragraphs", []) or []

    # Rule 1 — required keys
    for p in paragraphs:
        name = p.get("paragraph", "<unnamed>")
        missing = _REQUIRED_KEYS - set(p.keys())
        if missing:
            _fail(report, name, "SCHEMA",
                  f"missing keys: {sorted(missing)}")

    # Rule 2 — terminator in allowed set
    for p in paragraphs:
        t = p.get("terminator")
        if t not in _VALID_TERMINATORS:
            _fail(report, p.get("paragraph", "<unnamed>"), "TERMINATOR-SET",
                  f"terminator '{t}' not in {sorted(_VALID_TERMINATORS)}")

    # Rule 3 — implicit ↔ falls_through_to == next paragraph name.
    # Build next-name lookup by source order.
    ordered = sorted(
        [p for p in paragraphs if "first_line" in p],
        key=lambda q: q.get("first_line", 0),
    )
    name_by_order = [p.get("paragraph") for p in ordered]
    for idx, p in enumerate(ordered):
        name = p.get("paragraph")
        t = p.get("terminator")
        ft = p.get("falls_through_to")
        next_name = name_by_order[idx + 1] if idx + 1 < len(name_by_order) else None
        if t == "implicit":
            if ft is None:
                _fail(report, name, "FT-IMPLICIT",
                      "terminator='implicit' but falls_through_to is null")
            elif ft != next_name:
                _fail(report, name, "FT-IMPLICIT",
                      f"falls_through_to='{ft}' does not match next "
                      f"paragraph in source order ('{next_name}')")
        else:
            if ft is not None:
                _fail(report, name, "FT-NON-IMPLICIT",
                      f"terminator='{t}' requires falls_through_to=null, "
                      f"got '{ft}'")

    # Rule 4 — last paragraph must not be 'implicit'
    if ordered:
        last = ordered[-1]
        if last.get("terminator") == "implicit":
            _fail(report, last.get("paragraph"), "LAST-PARAGRAPH",
                  "last paragraph in source has terminator='implicit' "
                  "(no successor to fall to)")

    # Rule 5 — source-order guard
    for i in range(len(ordered) - 1):
        a = ordered[i]
        b = ordered[i + 1]
        if not (b.get("first_line", 0) > a.get("last_line", 0)):
            _fail(report, a.get("paragraph"), "C-5-ORDER",
                  f"first_line[{b.get('paragraph')}]={b.get('first_line')} "
                  f"is not > last_line[{a.get('paragraph')}]="
                  f"{a.get('last_line')}")

    # Rule 6 — artifact self-report
    if artifact.get("c5_assertion") != "PASS":
        _fail(report, "<file>", "C-5-SELF-REPORT",
              f"artifact c5_assertion='{artifact.get('c5_assertion')}' "
              f"(expected 'PASS')")
    v = artifact.get("c5_violations", [])
    if v:
        _fail(report, "<file>", "C-5-SELF-REPORT",
              f"artifact c5_violations list is non-empty: {v}")

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_fallthrough.py",
        description="T-PASS1-FT 100%-blocking validator (LLM-FREE).",
    )
    parser.add_argument("--fallthrough", required=True,
                        help="fallthrough JSON (chunk (c) extractor output)")
    parser.add_argument("--out", required=True,
                        help="Report JSON output path")
    args = parser.parse_args(argv)

    try:
        with open(args.fallthrough) as f:
            artifact = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.fallthrough}: {e}", file=sys.stderr)
        return 1

    report = validate(artifact)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    prog = report["program"]
    if report["pass"]:
        print(f"PASS T-PASS1-FT {prog} → {args.out}")
        return 0
    else:
        print(f"FAIL T-PASS1-FT {prog} "
              f"({len(report['failures'])} failure(s)) → {args.out}",
              file=sys.stderr)
        for fail in report["failures"][:10]:
            print(f"  - [{fail['rule']}] {fail['paragraph']}: {fail['detail']}",
                  file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
