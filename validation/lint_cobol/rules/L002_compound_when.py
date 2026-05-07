"""
L002 — Compound WHEN: mixed boolean condition-name AND relational comparison

Severity : ERROR
Layer    : 2 — Static Analysis (pre-smojol-cli, pre-GnuCOBOL)
Classif. : Type A — smojol-cli EvaluateBreaker / AdditionalConditionVisitor crash pattern

Pattern detected:
    WHEN <condition-name-88>(<subscript>)
         AND <data-name> EQUAL|... <literal>

This causes NullPointerException in smojol-cli
EvaluateBreaker.java:77 / AdditionalConditionVisitor.java:50.

Fix: split into two WHEN clauses or restructure using nested IF inside WHEN.

Documented in:
    docs/audit/COBOL_SOURCE_MODIFICATION_AUDIT.md
    PR #27
"""

import re

RULE_ID     = "L002"
SEVERITY    = "ERROR"
DESCRIPTION = "Compound WHEN mixes boolean condition-name AND relational comparison (smojol-cli crash)"

_WHEN_BOOL = re.compile(r'^\s{6,}WHEN\s+[A-Z][A-Z0-9-]*(?:\([^)]+\))?\s*$', re.IGNORECASE)
_AND_REL   = re.compile(
    r'^\s{6,}AND\s+[A-Z][A-Z0-9-]+\s+(?:EQUAL|NOT\s+EQUAL|GREATER|LESS|>|<|>=|<=)',
    re.IGNORECASE
)


def check(program_name: str, lines: list[str]) -> list[dict]:
    findings = []
    for i, line in enumerate(lines):
        if _WHEN_BOOL.match(line):
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j]
                if next_line.strip().startswith('*'):
                    continue
                if _AND_REL.match(next_line):
                    findings.append({
                        "rule":     RULE_ID,
                        "severity": SEVERITY,
                        "file":     program_name,
                        "line":     i + 1,
                        "message":  (
                            f"Compound WHEN..AND at line {i+1}: "
                            f"{line.strip()!r} followed by {next_line.strip()!r}. "
                            "Restructure using nested IF inside WHEN (Type A rewrite)."
                        )
                    })
                break
    return findings
