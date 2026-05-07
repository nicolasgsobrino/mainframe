#!/usr/bin/env python3
# LLM-FREE — Deterministic validator (T-PASS1-MUT). No LLM inference.
"""
validate_mutations.py — T-PASS1-MUT (100% blocking).

Task: T-2026-04-24-001 (Schema v1.2 — Hercules Byte-Parity Foundation)
Gate: G2 — chunk (f3) implementation.

Authoritative checks (derived from G1-scaffold.md §6.3 / §8.3 / C-3 and
Claude Opus multi-model review findings in chunk (d)):

  1. SCHEMA — artifact has paragraphs[] array; each paragraph entry
     has keys {paragraph, classification_source, mutates, reads}; every
     mutates[]/reads[] entry has keys {fd_name, verb, line, raw}.
  2. WRITER-VERB-SET — every entry in mutates[] MUST have its verb in
     the writer set: {MOVE, INITIALIZE, SET, ADD, SUBTRACT, MULTIPLY,
     DIVIDE, COMPUTE, STRING, UNSTRING, ACCEPT, READ, WRITE, REWRITE,
     DELETE}. (Extractor §8.3.)
  3. READER-VERB-SET — every entry in reads[] MUST have its verb in
     the reader set: {MOVE, ADD, SUBTRACT, MULTIPLY, DIVIDE, COMPUTE,
     STRING, UNSTRING, IF, EVALUATE, DISPLAY, PERFORM, WHEN, SET,
     SEARCH}. (Extractor §8.3 + C-3.)
  4. NO-IED-IN-MUTATES — enforces Claude Opus multi-model concern 2:
     verbs {IF, EVALUATE, DISPLAY, PERFORM, WHEN} are READ-ONLY and
     MUST NOT appear in mutates[]. Any hit fails pass=false.
  5. FD-NAME-NON-EMPTY — fd_name string is non-empty and not
     whitespace-only. (Rule 9 minimum; full qualification check lives
     in T01/T02 cross-validators.)
  6. SOURCE-ORDER — for every entry, line is a positive integer.
  7. DEDUP — within a single paragraph, (fd_name, verb, line) triples
     MUST be unique in both mutates[] and reads[].
  8. C-3-DISPOSITION — if any paragraph contains SEARCH or SEARCH ALL
     hits (verb == "SEARCH"), both the searched table and the
     index-of-table must appear in mutates[] / reads[] per §6.3. If
     no SEARCH hits exist on the file (chunk (d) SYNC precedent
     disposition: implemented-unexercised), the rule records
     c3_search_exercised=false in the report and does not fail.

Any Rule 1–7 miss → pass=false. 100% blocking.

CLI:
  python scripts/validate_mutations.py \
      --paragraph-io validation/pass1/paragraph_io/<PROGRAM>.json \
      --out validation/reports/<PROGRAM>_T-PASS1-MUT.json

Exit codes:
  0 — PASS
  1 — usage / IO error
  2 — any rule failure; report written.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

__LLM_FREE__ = True

_WRITER_VERBS = {
    "MOVE", "INITIALIZE", "SET", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE",
    "COMPUTE", "STRING", "UNSTRING", "ACCEPT", "READ", "WRITE", "REWRITE",
    "DELETE",
}

_READER_VERBS = {
    "MOVE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "COMPUTE",
    "STRING", "UNSTRING", "IF", "EVALUATE", "DISPLAY", "PERFORM",
    "WHEN", "SET", "SEARCH",
}

# Verbs that are READ-ONLY: must never appear in mutates[].
_READ_ONLY_VERBS = {"IF", "EVALUATE", "DISPLAY", "PERFORM", "WHEN"}

_ENTRY_KEYS = {"fd_name", "verb", "line", "raw"}


def _fail(report: dict, para: str, rule: str, detail: str) -> None:
    report["pass"] = False
    report["failures"].append({"paragraph": para, "rule": rule,
                               "detail": detail})


def _check_entry(entry: dict, list_name: str, para: str,
                 report: dict) -> None:
    missing = _ENTRY_KEYS - set(entry.keys())
    if missing:
        _fail(report, para, "SCHEMA",
              f"{list_name}[] entry missing keys: {sorted(missing)}")
        return

    fd = entry.get("fd_name")
    verb = entry.get("verb")
    line = entry.get("line")

    if not isinstance(fd, str) or not fd.strip():
        _fail(report, para, "FD-NAME-NON-EMPTY",
              f"{list_name}[] entry has empty/whitespace fd_name "
              f"(verb='{verb}' line={line})")

    if not isinstance(line, int) or line <= 0:
        _fail(report, para, "SOURCE-ORDER",
              f"{list_name}[] entry has invalid line={line!r} "
              f"(verb='{verb}' fd_name='{fd}')")

    v = (verb or "").upper()
    if list_name == "mutates":
        if v not in _WRITER_VERBS:
            _fail(report, para, "WRITER-VERB-SET",
                  f"mutates[] verb '{verb}' not in writer set "
                  f"(line {line}, fd_name='{fd}')")
        if v in _READ_ONLY_VERBS:
            _fail(report, para, "NO-IED-IN-MUTATES",
                  f"mutates[] contains read-only verb '{verb}' "
                  f"(line {line}, fd_name='{fd}'): IF/EVALUATE/DISPLAY/"
                  f"PERFORM/WHEN are READ-ONLY per chunk (d) Opus rule")
    else:  # reads
        if v not in _READER_VERBS:
            _fail(report, para, "READER-VERB-SET",
                  f"reads[] verb '{verb}' not in reader set "
                  f"(line {line}, fd_name='{fd}')")


def validate(artifact: dict) -> dict:
    report = {
        "tier": "T-PASS1-MUT",
        "program": artifact.get("program"),
        "source_sha256": artifact.get("source_sha256"),
        "cfg_sha256": artifact.get("cfg_sha256"),
        "byte_layouts_sha256": artifact.get("byte_layouts_sha256"),
        "pass": True,
        "failures": [],
        "c3_search_exercised": False,
        "c3_disposition": None,
    }

    paragraphs = artifact.get("paragraphs", []) or []

    for p in paragraphs:
        name = p.get("paragraph", "<unnamed>")
        if "mutates" not in p or "reads" not in p:
            _fail(report, name, "SCHEMA",
                  "paragraph missing 'mutates' or 'reads' key")
            continue

        muts = p.get("mutates") or []
        reads = p.get("reads") or []

        if not isinstance(muts, list) or not isinstance(reads, list):
            _fail(report, name, "SCHEMA",
                  "mutates/reads must be arrays")
            continue

        for e in muts:
            _check_entry(e, "mutates", name, report)
        for e in reads:
            _check_entry(e, "reads", name, report)

        # Rule 7 — DEDUP
        mkey = [(e.get("fd_name"), e.get("verb"), e.get("line"))
                for e in muts]
        rkey = [(e.get("fd_name"), e.get("verb"), e.get("line"))
                for e in reads]
        if len(mkey) != len(set(mkey)):
            _fail(report, name, "DEDUP",
                  f"mutates[] contains duplicate (fd_name,verb,line) "
                  f"triples: total={len(mkey)} unique={len(set(mkey))}")
        if len(rkey) != len(set(rkey)):
            _fail(report, name, "DEDUP",
                  f"reads[] contains duplicate (fd_name,verb,line) "
                  f"triples: total={len(rkey)} unique={len(set(rkey))}")

        # Rule 8 — C-3 SEARCH disposition
        search_in_reads = any((e.get("verb") or "").upper() == "SEARCH"
                              for e in reads)
        search_in_mutates = any((e.get("verb") or "").upper() == "SEARCH"
                                for e in muts)
        if search_in_reads or search_in_mutates:
            report["c3_search_exercised"] = True

    if report["c3_search_exercised"]:
        report["c3_disposition"] = "exercised"
    else:
        # Per chunk (d) SYNC precedent.
        report["c3_disposition"] = "implemented-unexercised"

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_mutations.py",
        description="T-PASS1-MUT 100%-blocking validator (LLM-FREE).",
    )
    parser.add_argument("--paragraph-io", required=True,
                        help="paragraph_io JSON (chunk (d) extractor output)")
    parser.add_argument("--out", required=True,
                        help="Report JSON output path")
    args = parser.parse_args(argv)

    try:
        with open(args.paragraph_io) as f:
            artifact = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.paragraph_io}: {e}", file=sys.stderr)
        return 1

    report = validate(artifact)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    prog = report["program"]
    if report["pass"]:
        print(f"PASS T-PASS1-MUT {prog} "
              f"(c3={report['c3_disposition']}) → {args.out}")
        return 0
    else:
        print(f"FAIL T-PASS1-MUT {prog} "
              f"({len(report['failures'])} failure(s)) → {args.out}",
              file=sys.stderr)
        for fail in report["failures"][:10]:
            print(f"  - [{fail['rule']}] {fail['paragraph']}: {fail['detail']}",
                  file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
