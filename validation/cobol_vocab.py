#!/usr/bin/env python3
"""
cobol_vocab.py -- shared COBOL reserved-word vocabulary for the validation pipeline.

Import from any validation script instead of redefining locally:

    from validation.cobol_vocab import COBOL_SCOPE_TERMINATORS

This is the single source of truth.  extract_ground_truth.py, lint_md.py,
extract_md_claims.py, and gate_compare.py all import from here.
"""

# Structured-statement scope terminators.
# Cobol-REKT RC8 false positive: these are misidentified as paragraph labels
# and reported as dead code OR reachable paragraphs depending on program
# structure.  They are filtered from BOTH lists in extract_ground_truth.py
# and must never appear as paragraph names in gold-candidate MD frontmatter.
COBOL_SCOPE_TERMINATORS: frozenset = frozenset({
    "END-EXEC",
    "END-IF",
    "END-PERFORM",
    "END-EVALUATE",
    "END-READ",
    "END-WRITE",
    "END-STRING",
    "END-UNSTRING",
    "END-MULTIPLY",
    "END-DIVIDE",
    "END-ADD",
    "END-SUBTRACT",
    "END-COMPUTE",
    "END-SEARCH",
    "END-CALL",
    "END-REWRITE",
    "END-DELETE",
    "END-START",
    "END-RETURN",
})

# Additional COBOL reserved words that are never valid paragraph names.
# Extend as new false-positive patterns are discovered.
# NOTE: GOBACK is intentionally excluded -- it is a legitimate paragraph
# name used in CardDemo programs and must not be linted as invalid.
COBOL_RESERVED_NOT_PARAGRAPHS: frozenset = frozenset({
    "SECTION",
    "DIVISION",
    "DECLARATIVES",
    "END",
    "STOP",
    "EXIT",
    "CONTINUE",
    "NEXT",
    "SENTENCE",
})

# Combined blocklist used by lint_md.py and gate_compare.py
INVALID_PARAGRAPH_NAMES: frozenset = COBOL_SCOPE_TERMINATORS | COBOL_RESERVED_NOT_PARAGRAPHS
