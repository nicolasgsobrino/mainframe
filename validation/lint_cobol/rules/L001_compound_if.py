"""
L001 — Compound IF: mixed boolean condition-name AND relational comparison

Severity : ERROR
Layer    : 2 — Static Analysis (pre-smojol-cli, pre-GnuCOBOL)
Classif. : Type A — smojol-cli ConditionVisitor crash pattern

Pattern detected:
    IF  <condition-name-88>(<subscript>)
    AND <data-name> EQUAL|NOT EQUAL|> |< <literal>

This exact pattern causes a NullPointerException in smojol-cli
ConditionVisitor.java:28 / IfFlowNode.java:93 because the visitor
resolves the 88-level condition-name as boolean but then calls
.getRelationalOperation() on the AND-operand, which returns null
for mixed boolean+relational compounds.

Fix: decompose into two separate nested IF statements (Type A rewrite).

Documented in:
    docs/audit/COBOL_SOURCE_MODIFICATION_AUDIT.md
    PRs #27, #28
"""

import re

RULE_ID     = "L001"
SEVERITY    = "ERROR"
DESCRIPTION = "Compound IF mixes boolean condition-name AND relational comparison (smojol-cli crash)"

# Matches: IF <TOKEN>(subscript) or IF <TOKEN>  — where the next non-blank line contains AND
_IF_BOOL  = re.compile(r'^\s{6,}IF\s+[A-Z][A-Z0-9-]*(?:\([^)]+\))?\s*$', re.IGNORECASE)
_AND_REL  = re.compile(
    r'^\s{6,}AND\s+[A-Z][A-Z0-9-]+\s+(?:EQUAL|NOT\s+EQUAL|GREATER|LESS|>|<|>=|<=)',
    re.IGNORECASE
)


def check(program_name: str, lines: list[str]) -> list[dict]:
    findings = []
    for i, line in enumerate(lines):
        if _IF_BOOL.match(line):
            # Look ahead up to 3 lines for an AND relational
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j]
                if next_line.strip().startswith('*'):  # skip comment lines
                    continue
                if _AND_REL.match(next_line):
                    findings.append({
                        "rule":     RULE_ID,
                        "severity": SEVERITY,
                        "file":     program_name,
                        "line":     i + 1,
                        "message":  (
                            f"Compound IF..AND at line {i+1}: "
                            f"{line.strip()!r} followed by {next_line.strip()!r}. "
                            "Decompose into two separate nested IF statements (Type A rewrite)."
                        )
                    })
                break  # only check first non-comment continuation
    return findings
