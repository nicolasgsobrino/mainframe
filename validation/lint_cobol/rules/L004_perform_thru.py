"""
L004 — PERFORM..THRU targeting non-adjacent paragraph pairs

Severity : INFO
Layer    : 2 — Static Analysis
Classif. : Structural risk — GnuCOBOL fall-through behaviour

Pattern detected:
    PERFORM <PARA-A>
       THRU <PARA-B>

...where PARA-A and PARA-B do not appear adjacent in the source.

PERFORM..THRU in IBM COBOL executes all paragraphs between PARA-A and
PARA-B in source order, including any paragraphs in between. This is
legal but dangerous: if new paragraphs are inserted between the two
targets, they silently become part of the execution path.

GnuCOBOL implements PERFORM..THRU identically to IBM COBOL, so this
is not a compilation error — it is a maintainability and audit flag.

This rule is INFO-only. It records every PERFORM..THRU pair so that
human reviewers can verify the intended paragraph ranges during the
pre-GnuCOBOL review phase.
"""

import re

RULE_ID     = "L004"
SEVERITY    = "INFO"
DESCRIPTION = "PERFORM..THRU detected — verify paragraph adjacency before GnuCOBOL compile"

_PERFORM_THRU = re.compile(
    r'^\s{6,}PERFORM\s+([A-Z][A-Z0-9-]+)\s*$',
    re.IGNORECASE
)
_THRU_LINE = re.compile(
    r'^\s{6,}THRU\s+([A-Z][A-Z0-9-]+)',
    re.IGNORECASE
)
# Also catch single-line: PERFORM X THRU Y
_PERFORM_THRU_INLINE = re.compile(
    r'^\s{6,}PERFORM\s+([A-Z][A-Z0-9-]+)\s+THRU\s+([A-Z][A-Z0-9-]+)',
    re.IGNORECASE
)


def check(program_name: str, lines: list[str]) -> list[dict]:
    findings = []
    for i, line in enumerate(lines):
        # Single-line form: PERFORM A THRU B
        m = _PERFORM_THRU_INLINE.match(line)
        if m:
            para_a, para_b = m.group(1).upper(), m.group(2).upper()
            findings.append({
                "rule":     RULE_ID,
                "severity": SEVERITY,
                "file":     program_name,
                "line":     i + 1,
                "message":  (
                    f"PERFORM {para_a} THRU {para_b} at line {i+1}. "
                    "Verify paragraph adjacency — all paragraphs between these "
                    "two are included in the execution path."
                )
            })
            continue

        # Two-line form: PERFORM A \n THRU B
        m = _PERFORM_THRU.match(line)
        if m:
            para_a = m.group(1).upper()
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j]
                if next_line.strip().startswith('*') or not next_line.strip():
                    continue
                m2 = _THRU_LINE.match(next_line)
                if m2:
                    para_b = m2.group(1).upper()
                    findings.append({
                        "rule":     RULE_ID,
                        "severity": SEVERITY,
                        "file":     program_name,
                        "line":     i + 1,
                        "message":  (
                            f"PERFORM {para_a} THRU {para_b} at line {i+1}. "
                            "Verify paragraph adjacency — all paragraphs between these "
                            "two are included in the execution path."
                        )
                    })
                break
    return findings
