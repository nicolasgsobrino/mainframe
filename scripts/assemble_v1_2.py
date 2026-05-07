#!/usr/bin/env python3
# LLM-FREE — Deterministic Markdown assembly from T-001 front-matter +
# LLM-FREE — v1.2 extractor outputs. No LLM inference.
"""
assemble_v1_2.py — Emit translations/baseline-v1.2/<PROGRAM>.md by inheriting
T-001 front-matter and appending optional v1.2 Hercules byte-parity sections.

Task: T-2026-04-24-001 (Schema v1.2 — Hercules Byte-Parity Foundation)
Gate: G2 — chunk (g) implementation.

Authoritative rules (verbatim from G1-scaffold.md §6.5 / §8.5 / §8.6 and
MASTER-ARCHITECTURE.md v1.0.0):

    Front-matter inheritance:
      Read translations/baseline/<PROGRAM>.md as the authoritative v1.0
      front-matter. Copy every field verbatim except schema_version →
      "cobol-md/1.2". All new v1.2 fields are OPTIONAL additions; ZERO
      existing fields may be mutated (G0 hard constraint #2 — backward
      compatibility).

    Optional v1.2 sections appended to front-matter YAML:
      byte_layout:            from extract_byte_layout.py sections tree
      fall_through:           from extract_fallthrough.py paragraphs
      paragraph_io:           from extract_paragraph_io.py paragraphs
      file_control:           enriched in place by logical_name / ddname
                              match; existing keys untouched, v1.2 keys
                              appended per entry
      memory_model:           §8.5 — {working_storage_bytes, linkage_bytes,
                                       global_memory, persistence}
      hercules_parity:        §8.6 + C-4 — {ready, jcl_reference,
                                       input_dataset_sha256,
                                       expected_output_sha256,
                                       actual_output_sha256 (C-4),
                                       byte_diff_report (C-4)}

    Write target: translations/baseline-v1.2/<PROGRAM>.md  (new directory).
    Do NOT modify translations/baseline/, gold-candidate/, or baseline-v1.1/.

    Prose body (after the closing front-matter "---") is copied BYTE-FOR-BYTE
    from the baseline. Hard-rule #7: no raw COBOL added — no fenced cobol
    blocks emitted; no PIC clauses appear in the assembler's generated YAML
    (encoded as "pic" data, not as verbatim COBOL).

    Validation block inherited unchanged: overall: PENDING, every tier null.
    G3 populates; the assembler never does.

CLI:
    python scripts/assemble_v1_2.py \
        --baseline-md   translations/baseline/<PROGRAM>.md \
        --byte-layout   validation/pass1/byte_layouts/<PROGRAM>.json \
        --fallthrough   validation/pass1/fallthrough/<PROGRAM>.json \
        --paragraph-io  validation/pass1/paragraph_io/<PROGRAM>.json \
        --file-control  validation/pass1/file_control/<PROGRAM>.json \
        --out           translations/baseline-v1.2/<PROGRAM>.md

Exit codes:
    0 — assembled OK
    1 — usage / IO / YAML parse error
    2 — hard-rule violation (would emit raw COBOL, would mutate baseline
        field, or sanity-check failed)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import yaml

__LLM_FREE__ = True

# ----------------------------------------------------------------------
# Front-matter split
# ----------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*(?:\n|$)", re.DOTALL)


def _split_md(md_text: str) -> tuple[str, str]:
    """Return (yaml_text, body_text). body_text starts after the closing ---
    and preserves leading whitespace exactly."""
    m = _FRONTMATTER_RE.match(md_text)
    if not m:
        raise ValueError("baseline MD has no YAML front-matter block")
    yaml_text = m.group(1)
    body_start = m.end()
    body_text = md_text[body_start:]
    return yaml_text, body_text


# ----------------------------------------------------------------------
# v1.2 section builders (pure transformations from extractor JSON)
# ----------------------------------------------------------------------

def _byte_layout_section(byte_layout: dict) -> dict:
    """Build top-level byte_layout section from extract_byte_layout output."""
    sections = byte_layout.get("sections", {}) or {}
    totals = byte_layout.get("totals", {}) or {}
    return {
        "file": sections.get("file", []) or [],
        "working_storage": sections.get("working_storage", []) or [],
        "linkage": sections.get("linkage", []) or [],
        "totals": {
            "working_storage_bytes": totals.get("working_storage_bytes", 0),
            "linkage_bytes": totals.get("linkage_bytes", 0),
        },
    }


def _fall_through_section(fallthrough: dict) -> dict:
    """Build fall_through section — preserve paragraph list + C-5 assertion."""
    return {
        "paragraphs": fallthrough.get("paragraphs", []) or [],
        "c5_assertion": fallthrough.get("c5_assertion", "PASS"),
        "c5_violations": fallthrough.get("c5_violations", 0),
    }


def _paragraph_io_section(paragraph_io: dict) -> list:
    """Build paragraph_io list — just the paragraphs array (metadata is
    embedded via source_sha256 pinning in the reports, not in the MD)."""
    return paragraph_io.get("paragraphs", []) or []


def _memory_model(byte_layout: dict) -> dict:
    """§8.5 memory_model."""
    totals = byte_layout.get("totals", {}) or {}
    return {
        "working_storage_bytes": totals.get("working_storage_bytes", 0),
        "linkage_bytes": totals.get("linkage_bytes", 0),
        "global_memory": True,
        "persistence": "process",
    }


def _hercules_parity() -> dict:
    """§8.6 + C-4 hercules_parity — all placeholders null / ready:false."""
    return {
        "ready": False,
        "jcl_reference": None,
        "input_dataset_sha256": None,
        "expected_output_sha256": None,
        # C-4 additions
        "actual_output_sha256": None,
        "byte_diff_report": None,
    }


# ----------------------------------------------------------------------
# file_control merge: v1.2 enrichment on existing entries
# ----------------------------------------------------------------------

# Keys the v1.2 extractor adds on top of the baseline file_control entries.
# Order matters for stable YAML emission.
_V12_FC_KEYS = (
    "logical_name",
    "file_status",
    "record_format",
    "record_length",
    "record_varying",
    "input_codepage",
    "codepage_default_applied",
    "sign_convention",
    "endianness",
)

# Keys the BASELINE file_control entry carries. These MUST NOT be mutated
# by the merge step.
_BASELINE_FC_KEYS = ("ddname", "organization", "access", "record_key", "crud")


def _merge_file_control(
    baseline_fc: list, v12_fc: list, *, program: str
) -> tuple[list, dict]:
    """Merge v1.2 extractor file_control onto baseline file_control.

    Match rule: baseline entries are matched to v1.2 entries by ddname.
    - Baseline keys are copied verbatim (no mutation).
    - v1.2 OPTIONAL keys are appended per entry.
    - v1.2 entries without a baseline match are NOT added as new entries
      (the baseline list is authoritative for the program). Instead, a
      sanity-check warning is raised in the trace dict. (This never
      happens on the pilot corpus per the chunk (e) corpus run.)
    - Baseline entries without a v1.2 match are kept unchanged and a
      warning is added.

    Returns (merged_list, trace_dict).
    """
    trace = {
        "baseline_count": len(baseline_fc or []),
        "v12_count": len(v12_fc or []),
        "merged": [],
        "baseline_only": [],
        "v12_only": [],
    }
    baseline_fc = baseline_fc or []
    v12_fc = v12_fc or []
    v12_by_dd = {e.get("ddname"): e for e in v12_fc if e.get("ddname")}
    out = []
    matched_v12 = set()
    for base in baseline_fc:
        dd = base.get("ddname")
        merged = dict(base)  # preserve baseline key ordering + values
        v12 = v12_by_dd.get(dd)
        if v12:
            matched_v12.add(dd)
            for k in _V12_FC_KEYS:
                if k in v12 and v12[k] is not None:
                    # Do not overwrite a baseline key with a v1.2 value on
                    # the same name — hard constraint #2.
                    if k in _BASELINE_FC_KEYS:
                        continue
                    merged[k] = v12[k]
            trace["merged"].append(dd)
        else:
            trace["baseline_only"].append(dd)
        out.append(merged)
    for dd, v12 in v12_by_dd.items():
        if dd not in matched_v12:
            trace["v12_only"].append(dd)
    return out, trace


# ----------------------------------------------------------------------
# Front-matter assembly
# ----------------------------------------------------------------------

def assemble_front_matter(
    baseline_fm: dict,
    byte_layout: dict,
    fallthrough: dict,
    paragraph_io: dict,
    file_control_v12: dict,
) -> tuple[dict, dict]:
    """Return (new_front_matter_dict, trace_dict).

    The new dict is a fresh ordered dict that (a) copies every baseline key
    in baseline order, (b) bumps schema_version, (c) enriches file_control[]
    entries in place, (d) appends v1.2-only sections before the validation
    block (validation stays last — G3 populates).
    """
    trace: dict = {}

    # Start by copying baseline keys verbatim, preserving insertion order.
    new_fm: dict = {}
    validation_value = None
    pending_ordered_keys = []
    for k, v in baseline_fm.items():
        if k == "validation":
            validation_value = v
            continue
        new_fm[k] = v
        pending_ordered_keys.append(k)

    # (b) bump schema_version
    if "schema_version" not in new_fm:
        raise ValueError("baseline front-matter missing schema_version")
    prev = new_fm["schema_version"]
    new_fm["schema_version"] = "cobol-md/1.2"
    trace["schema_version_bump"] = {"from": prev, "to": "cobol-md/1.2"}

    # (c) file_control enrichment
    merged_fc, fc_trace = _merge_file_control(
        new_fm.get("file_control") or [],
        (file_control_v12 or {}).get("file_control") or [],
        program=baseline_fm.get("program_id", ""),
    )
    new_fm["file_control"] = merged_fc
    trace["file_control"] = fc_trace

    # (d) append v1.2-only OPTIONAL sections BEFORE the validation block
    new_fm["byte_layout"] = _byte_layout_section(byte_layout or {})
    new_fm["fall_through"] = _fall_through_section(fallthrough or {})
    new_fm["paragraph_io"] = _paragraph_io_section(paragraph_io or {})
    new_fm["memory_model"] = _memory_model(byte_layout or {})
    new_fm["hercules_parity"] = _hercules_parity()

    # (e) put validation block last, verbatim
    if validation_value is not None:
        new_fm["validation"] = validation_value

    trace["ordered_keys"] = list(new_fm.keys())
    return new_fm, trace


# ----------------------------------------------------------------------
# YAML emission + hard-rule post-checks
# ----------------------------------------------------------------------

class _Emitter(yaml.SafeDumper):
    pass


def _repr_none(dumper, _):
    return dumper.represent_scalar("tag:yaml.org,2002:null", "null")


_Emitter.add_representer(type(None), _repr_none)


def _emit_yaml(fm: dict) -> str:
    return yaml.dump(
        fm,
        Dumper=_Emitter,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=120,
    )


_COBOL_FENCE_RE = re.compile(r"```\s*cobol", re.IGNORECASE)
_COBOL_PIC_RE = re.compile(
    r"^\s*[A-Z0-9\-]+\s+PIC(?:TURE)?\s+\S+\.\s*$", re.MULTILINE
)


def _hard_rule_check(md_text: str) -> list[str]:
    """Re-check the T01 hard rules: no fenced cobol, no raw COBOL PIC lines
    at prose level. Front-matter carries PIC data inside YAML strings, which
    is allowed; the PIC-clause heuristic matches standalone lines only."""
    violations: list[str] = []
    if _COBOL_FENCE_RE.search(md_text):
        violations.append("fenced cobol code block found")
    # Split body off front-matter; only inspect body for standalone PIC lines
    m = _FRONTMATTER_RE.match(md_text)
    body = md_text[m.end():] if m else md_text
    if _COBOL_PIC_RE.search(body):
        violations.append("raw COBOL PIC clause found in prose body")
    return violations


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="assemble_v1_2.py",
        description=(
            "Assemble v1.2 Markdown by inheriting T-001 front-matter and "
            "appending optional byte-parity sections (LLM-FREE)."
        ),
    )
    parser.add_argument("--baseline-md", required=True,
                        help="T-001 v1.0 baseline .md (read-only)")
    parser.add_argument("--byte-layout", required=True,
                        help="byte_layout JSON (chunk b)")
    parser.add_argument("--fallthrough", required=True,
                        help="fallthrough JSON (chunk c)")
    parser.add_argument("--paragraph-io", required=True,
                        help="paragraph_io JSON (chunk d)")
    parser.add_argument("--file-control", required=True,
                        help="file_control JSON (chunk e)")
    parser.add_argument("--out", required=True,
                        help="Output .md path under translations/baseline-v1.2/")
    parser.add_argument("--trace", default=None,
                        help="Optional: write JSON trace of the merge here")
    args = parser.parse_args(argv)

    # Load baseline MD — NEVER open for write. This path is read-only.
    try:
        baseline_text = open(args.baseline_md, "r", encoding="utf-8").read()
    except OSError as e:
        print(f"error: cannot read baseline MD: {e}", file=sys.stderr)
        return 1

    try:
        yaml_text, body_text = _split_md(baseline_text)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        baseline_fm = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as e:
        print(f"error: baseline YAML parse: {e}", file=sys.stderr)
        return 1

    def _load(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    try:
        bl = _load(args.byte_layout)
        ft = _load(args.fallthrough)
        pio = _load(args.paragraph_io)
        fc = _load(args.file_control)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot load extractor output: {e}", file=sys.stderr)
        return 1

    # Cross-check: program_id alignment. All four extractor JSONs carry
    # "program" or "program_id"; the baseline carries "program_id". If any
    # disagree, hard-stop (G0 constraint #2 sanity check).
    baseline_pid = baseline_fm.get("program_id")
    for label, obj in (("byte_layout", bl), ("fallthrough", ft),
                       ("paragraph_io", pio), ("file_control", fc)):
        p = obj.get("program") or obj.get("program_id")
        if p and baseline_pid and p != baseline_pid:
            print(
                f"error: {label} program mismatch: {p!r} vs "
                f"baseline {baseline_pid!r}",
                file=sys.stderr,
            )
            return 2

    new_fm, trace = assemble_front_matter(baseline_fm, bl, ft, pio, fc)

    # Emit
    out_yaml = _emit_yaml(new_fm)
    out_text = "---\n" + out_yaml + "---\n" + body_text
    # The baseline body starts with a single "\n" after the closing "---"
    # which we already strip in split_md; preserve as-is.

    # Hard-rule post-check
    violations = _hard_rule_check(out_text)
    if violations:
        print(f"error: hard-rule violations: {violations}", file=sys.stderr)
        return 2

    # Write
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(out_text)

    if args.trace:
        os.makedirs(os.path.dirname(args.trace) or ".", exist_ok=True)
        with open(args.trace, "w", encoding="utf-8") as fh:
            json.dump(trace, fh, indent=2)
            fh.write("\n")

    print(
        f"ASSEMBLED {baseline_pid} v1.2 → {args.out} "
        f"(file_control: {trace['file_control']['baseline_count']} baseline, "
        f"{trace['file_control']['v12_count']} v12, "
        f"merged={len(trace['file_control']['merged'])}, "
        f"baseline_only={len(trace['file_control']['baseline_only'])}, "
        f"v12_only={len(trace['file_control']['v12_only'])})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
