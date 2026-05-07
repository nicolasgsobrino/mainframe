#!/usr/bin/env python3
"""
extract_md_claims.py -- extract structural claims from a gold-candidate MD file.

Reads:  translations/gold-candidate/{PROGRAM}.md
Writes: validation/claims/{PROGRAM}_claims.json
        validation/logs/claims_{TIMESTAMP}.log    (append-only run log)

No LLM. Parses YAML frontmatter only -- no interpretation of prose body.
Runnable on any machine with Python 3.8+ and PyYAML.

Install deps:  pip install pyyaml

Usage:
    python validation/extract_md_claims.py              # all programs (auto-discovered)
    python validation/extract_md_claims.py CBACT01C     # single program

Run AFTER lint_md.py.
"""
import io
import json
import sys
import hashlib
import datetime
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except AttributeError:
    pass

try:
    import yaml
except ImportError:
    sys.exit("[CLAIMS] ERROR: PyYAML not installed. Run: pip install pyyaml")

try:
    from validation.cobol_vocab import INVALID_PARAGRAPH_NAMES
except ImportError:
    try:
        from cobol_vocab import INVALID_PARAGRAPH_NAMES
    except ImportError:
        INVALID_PARAGRAPH_NAMES = frozenset({
            "END-EXEC", "END-IF", "END-PERFORM", "END-EVALUATE",
            "END-READ", "END-WRITE", "END-STRING", "END-UNSTRING",
            "END-MULTIPLY", "END-DIVIDE", "END-ADD", "END-SUBTRACT",
            "END-COMPUTE", "END-SEARCH", "END-CALL", "END-REWRITE",
            "END-DELETE", "END-START", "END-RETURN",
        })


def _discover_programs() -> list[str]:
    """Auto-discover programs that have an MD file in translations/gold-candidate/."""
    gc_dir = Path("translations/gold-candidate")
    if not gc_dir.exists():
        return []
    return sorted(p.stem for p in gc_dir.glob("*.md"))


def log(run_id: str, lines: list, log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"claims_{run_id}.log"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return log_path


def parse_frontmatter(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8")
    parts = text.split("---")
    if len(parts) < 3:
        raise ValueError(f"No valid --- frontmatter in {md_path}")
    return yaml.safe_load(parts[1]) or {}


def extract(program_id: str) -> dict:
    md_path = Path(f"translations/gold-candidate/{program_id}.md")
    if not md_path.exists():
        print(f"[CLAIMS] ERROR: {md_path} not found -- skipping {program_id}")
        return {}, ""

    md_bytes = md_path.read_bytes()
    fm = parse_frontmatter(md_path)

    proc = fm.get("procedure_paragraphs", [])
    if not isinstance(proc, list):
        proc = []

    para_names = sorted(
        p["name"] if isinstance(p, dict) else str(p)
        for p in proc
    )
    dead_declared = sorted(
        p["name"]
        for p in proc
        if isinstance(p, dict) and p.get("reachable") is False
    )
    synthetic_paragraphs = sorted(
        p["name"]
        for p in proc
        if isinstance(p, dict) and p.get("synthetic") is True
    )

    lint_warnings = sorted(
        name for name in para_names
        if name.upper() in INVALID_PARAGRAPH_NAMES
    )

    items = fm.get("data_items", [])
    if not isinstance(items, list):
        items = []
    l01_names = sorted(
        d["name"]
        for d in items
        if isinstance(d, dict) and d.get("level") == 1
    )
    redefines = sorted(
        [d["name"], d["redefines"]]
        for d in items
        if isinstance(d, dict) and d.get("redefines")
    )

    calls_raw = fm.get("calls_to", [])
    calls = sorted(
        c["program"] if isinstance(c, dict) else str(c)
        for c in (calls_raw if isinstance(calls_raw, list) else [])
    )
    cpyb_raw = fm.get("copybooks_used", [])
    copybooks = sorted(
        c["name"] if isinstance(c, dict) else str(c)
        for c in (cpyb_raw if isinstance(cpyb_raw, list) else [])
    )
    cics = fm.get("cics_commands", [])

    val = fm.get("validation", {})
    if not isinstance(val, dict):
        val = {}
    t04_score = val.get("t04_semantic_score", None)

    claims = {
        "program_id": program_id,
        "md_sha": hashlib.sha256(md_bytes).hexdigest()[:12],
        "extracted_at": datetime.datetime.utcnow().isoformat() + "Z",
        "paragraphs_claimed": para_names,
        "dead_declared_in_md": dead_declared,
        "synthetic_paragraphs": synthetic_paragraphs,
        "lint_warnings": lint_warnings,
        "data_items_level01": l01_names,
        "redefines_pairs": redefines,
        "calls_to": calls,
        "copybooks": copybooks,
        "cics_commands": cics if isinstance(cics, list) else [],
        "t04_score_in_md": t04_score,
        "t04_score_is_null": t04_score is None,
    }

    out_path = Path(f"validation/claims/{program_id}_claims.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(claims, indent=2), encoding="utf-8")

    score_flag = "NULL [OK]" if t04_score is None else f"{t04_score} [!!] FABRICATED SCORE"
    synth_note = f", {len(synthetic_paragraphs)} synthetic" if synthetic_paragraphs else ""
    lint_note = f", {len(lint_warnings)} LINT WARNINGS" if lint_warnings else ""
    line = (
        f"[CLAIMS] {program_id}: "
        f"{len(para_names)} paragraphs{synth_note}{lint_note}, "
        f"{len(dead_declared)} dead declared, "
        f"{len(l01_names)} L01 items | "
        f"t04={score_flag}"
    )
    if lint_warnings:
        print(f"[CLAIMS] WARNING {program_id}: lint_warnings in claims -- invalid paragraph names: {lint_warnings}")
    print(line)
    return claims, line


if __name__ == "__main__":
    run_id = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    log_dir = Path("validation/logs")

    # Auto-discover all programs with a gold-candidate MD; explicit args override
    discovered = _discover_programs()
    targets = sys.argv[1:] if sys.argv[1:] else discovered

    # Warn only for programs that have no MD file
    unknown = [p for p in targets
               if not Path(f"translations/gold-candidate/{p}.md").exists()]
    run_lines = [f"# extract_md_claims run {run_id}", f"# targets: {targets}"]
    if unknown:
        warn = f"[CLAIMS] WARNING: no MD file found for: {unknown}"
        print(warn)
        run_lines.append(warn)

    for p in targets:
        if Path(f"translations/gold-candidate/{p}.md").exists():
            result = extract(p)
            if result:
                _, line = result
                run_lines.append(line)

    log(run_id, run_lines, log_dir)
    print(f"[CLAIMS] log written: validation/logs/claims_{run_id}.log")
