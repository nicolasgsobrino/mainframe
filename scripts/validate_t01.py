#!/usr/bin/env python3
"""T01 — Schema Validity. Threshold 100%."""
import argparse
import json
import re
import sys
from pathlib import Path
import yaml

REQUIRED_FIELDS = [
    "schema_version", "program_id", "source_file", "source_sha",
    "translation_date", "translating_agent", "aifirst_task_id", "cfg_source",
    "business_domain", "subtype", "calls_to", "called_by", "copybooks_used",
    "file_control", "data_items", "procedure_paragraphs", "business_rules", "validation",
]
BUSINESS_DOMAINS = [
    "Account Management", "Transaction Processing", "Customer Management",
    "Authorization", "Reporting", "Administration", "Utility", "Menu",
]
SUBTYPES = ["CICS-Online", "Batch", "Utility", "Menu", "Copybook"]
TASK_ID_RE = re.compile(r"^T-\d{4}-\d{2}-\d{2}-\d{3}$")

# Accepted schema versions. Kept as an immutable set so adding future
# versions (cobol-md/1.3, ...) is a one-line change. T-2026-04-24-001
# introduced v1.2 for the Hercules byte-parity schema additions; all prior
# versions remain valid so existing baseline/, baseline-v1.1/, and gold files
# continue to pass T01 without modification.
ACCEPTED_SCHEMA_VERSIONS = frozenset({
    "cobol-md/1.0",      # T-001 baseline
    "cobol-md/1.0.2",    # legal per docs v1.0.2 (reserved; not emitted today)
    "cobol-md/1.1",      # T-2026-04-23-002 baseline-v1.1
    "cobol-md/1.2",      # T-2026-04-24-001 baseline-v1.2 (Hercules byte-parity)
})


def validate(md_path: Path, repo_root: Path):
    content = md_path.read_text()
    parts = content.split("---", 2)
    errors = []
    if len(parts) < 3:
        return {"pass": False, "errors": ["No YAML front-matter found"]}
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        return {"pass": False, "errors": [f"YAML parse error: {e}"]}

    for f in REQUIRED_FIELDS:
        if f not in data:
            errors.append(f"Missing required field: {f}")

    if data.get("schema_version") not in ACCEPTED_SCHEMA_VERSIONS:
        errors.append(
            f"schema_version must be one of {sorted(ACCEPTED_SCHEMA_VERSIONS)} "
            f"(got {data.get('schema_version')!r})"
        )

    if data.get("business_domain") not in BUSINESS_DOMAINS:
        errors.append(f"Invalid business_domain: {data.get('business_domain')!r}")
    if data.get("subtype") not in SUBTYPES:
        errors.append(f"Invalid subtype: {data.get('subtype')!r}")

    cfg_src = data.get("cfg_source", "")
    if not (repo_root / cfg_src).exists():
        errors.append(f"cfg_source path does not exist: {cfg_src}")

    v = data.get("validation") or {}
    if v.get("overall") != "PENDING":
        errors.append(f"validation.overall must be PENDING at translation time (got {v.get('overall')!r})")

    tid = data.get("aifirst_task_id", "")
    if not TASK_ID_RE.match(str(tid)):
        errors.append(f"aifirst_task_id format invalid: {tid!r}")

    # No raw COBOL: no fenced cobol code block
    if re.search(r"```\s*cobol", content, re.IGNORECASE):
        errors.append("Raw COBOL fenced code block found in MD output (hard-rule violation)")
    # Heuristic: no DIVISION / SECTION / PIC/PICTURE + dot-terminated lines that look like verbatim COBOL
    suspicious = re.findall(r"^\s*[A-Z0-9\-]+\s+PIC(?:TURE)?\s+\S+\.\s*$", content, re.MULTILINE)
    if suspicious:
        errors.append(f"Possible raw COBOL PIC clauses detected ({len(suspicious)} occurrences)")

    return {"pass": len(errors) == 0, "errors": errors, "data": data}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = validate(Path(args.md), Path(args.repo_root))
    out = {
        "tier": "T01",
        "file": str(args.md),
        "pass": result["pass"],
        "errors": result["errors"],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out))
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
