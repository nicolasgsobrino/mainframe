"""
L003 — Fake/stub EXIT paragraph inserted for tool compatibility only

Severity : WARNING
Layer    : 2 — Static Analysis
Classif. : Type C — tool stub (must be stripped before production compile)

Pattern detected:
    <PARA-NAME>.
        EXIT
        .

...where the paragraph name ends in -EXIT and is immediately followed
by only an EXIT verb and a period, with no other statements.

Type C stubs exist solely to satisfy PERFORM..THRU targets or analysis
tool requirements. They are valid COBOL but must be flagged so they can
be reviewed before production deployment — some tools insert them
automatically and they may mask real missing logic.

Note: Many EXIT paragraphs are legitimate (e.g., genuine return points).
This rule flags only patterns where the ENTIRE paragraph body is
exactly one EXIT statement with no other verbs.
"""

import re

RULE_ID     = "L003"
SEVERITY    = "WARNING"
DESCRIPTION = "Stub EXIT paragraph (Type C — verify not a tool-inserted fake before production compile)"

_PARA_EXIT = re.compile(r'^\s{7}([A-Z][A-Z0-9-]*-EXIT)\.$', re.IGNORECASE)
_EXIT_VERB = re.compile(r'^\s+EXIT\s*\.?\s*$', re.IGNORECASE)
_PERIOD    = re.compile(r'^\s+\.\s*$')


def check(program_name: str, lines: list[str]) -> list[dict]:
    findings = []
    for i, line in enumerate(lines):
        m = _PARA_EXIT.match(line)
        if not m:
            continue
        para_name = m.group(1)
        # Check next 1-3 non-blank lines: if ALL are EXIT / period, it's a stub
        body_lines = []
        for j in range(i + 1, min(i + 6, len(lines))):
            stripped = lines[j].strip()
            if not stripped or stripped.startswith('*'):
                continue
            body_lines.append(stripped)
            if len(body_lines) >= 3:
                break

        if body_lines and all(
            re.match(r'^(EXIT\.?|\.)$', bl, re.IGNORECASE) for bl in body_lines
        ):
            findings.append({
                "rule":     RULE_ID,
                "severity": SEVERITY,
                "file":     program_name,
                "line":     i + 1,
                "message":  (
                    f"Stub EXIT paragraph '{para_name}' at line {i+1} "
                    "contains only EXIT. Verify this is not a tool-inserted fake "
                    "before production compile (Type C — strip if so)."
                )
            })
    return findings
