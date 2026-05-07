#!/usr/bin/env python3
"""
lint_md.py -- pre-commit MD linter for gold-candidate frontmatter.

Checks that no procedure_paragraph name in the MD file matches a known
COBOL scope terminator or reserved word that can never be a paragraph.

Exit codes:
    0 = lint PASS (safe to commit)
    1 = lint FAIL (bad paragraph names found -- do not commit)

Usage:
    python validation/lint_md.py CBACT01C
    python validation/lint_md.py                   # all programs
    python validation/lint_md.py CBACT01C COMEN01C  # subset

Add to agent task prompt:
    "Run python validation/lint_md.py {PROGRAM} before committing the MD.
     The command must exit 0. Fix any flagged paragraph names first."

Add to CI / manifest prereqs BEFORE extract_md_claims.py.
"""
import io
import sys
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except AttributeError:
    pass

try:
    import yaml
except ImportError:
    sys.exit("[LINT] ERROR: PyYAML not installed. Run: pip install pyyaml")

# ---------------------------------------------------------------------------
# Inline fallback so lint_md.py works even when run from repo root without
# the package on sys.path.  If cobol_vocab is importable, prefer that.
# ---------------------------------------------------------------------------
try:
    from validation.cobol_vocab import INVALID_PARAGRAPH_NAMES
except ImportError:
    try:
        from cobol_vocab import INVALID_PARAGRAPH_NAMES
    except ImportError:
        # Hard-coded fallback -- keep in sync with cobol_vocab.py
        INVALID_PARAGRAPH_NAMES = frozenset({
            "END-EXEC", "END-IF", "END-PERFORM", "END-EVALUATE",
            "END-READ", "END-WRITE", "END-STRING", "END-UNSTRING",
            "END-MULTIPLY", "END-DIVIDE", "END-ADD", "END-SUBTRACT",
            "END-COMPUTE", "END-SEARCH", "END-CALL", "END-REWRITE",
            "END-DELETE", "END-START", "END-RETURN",
            "SECTION", "DIVISION", "DECLARATIVES", "END", "STOP",
            "GOBACK", "EXIT", "CONTINUE", "NEXT", "SENTENCE",
        })

PROGRAMS = ["CBACT01C", "CBCUS01C", "CBTRN01C", "COBSWAIT", "COMEN01C", "COSGN00C", "CBSTM03A"]


def parse_frontmatter(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8")
    parts = text.split("---")
    if len(parts) < 3:
        raise ValueError(f"No valid --- frontmatter block in {md_path}")
    return yaml.safe_load(parts[1]) or {}


def lint(program_id: str) -> bool:
    """Returns True if lint passes, False if it fails."""
    md_path = Path(f"translations/gold-candidate/{program_id}.md")
    if not md_path.exists():
        print(f"[LINT] ERROR: {md_path} not found")
        return False

    try:
        fm = parse_frontmatter(md_path)
    except Exception as exc:
        print(f"[LINT] {program_id}: ERROR parsing frontmatter: {exc}")
        return False

    proc = fm.get("procedure_paragraphs", [])
    if not isinstance(proc, list):
        proc = []

    bad_names = []
    for entry in proc:
        name = entry["name"] if isinstance(entry, dict) else str(entry)
        if name.upper() in INVALID_PARAGRAPH_NAMES:
            bad_names.append(name)

    if bad_names:
        print(f"[LINT] FAIL {program_id}: invalid paragraph name(s) in procedure_paragraphs:")
        for n in bad_names:
            print(f"       - {n!r} is a COBOL scope terminator / reserved word, not a paragraph")
        print(f"[LINT] Remove or correct these entries before committing the MD.")
        return False

    print(f"[LINT] PASS {program_id}: all {len(proc)} paragraph name(s) are valid")
    return True


if __name__ == "__main__":
    targets = sys.argv[1:] if sys.argv[1:] else PROGRAMS
    unknown = [p for p in targets if p not in PROGRAMS]
    if unknown:
        print(f"[LINT] WARNING: unknown program(s): {unknown}")

    results = {}
    for p in targets:
        if p in PROGRAMS:
            results[p] = lint(p)

    total = len(results)
    passed = sum(results.values())
    print(f"\n[LINT] {passed}/{total} programs passed")

    sys.exit(0 if all(results.values()) else 1)
