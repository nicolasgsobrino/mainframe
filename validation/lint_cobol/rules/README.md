# Layer 2 Lint Rules — Catalogue

All rules in this directory are loaded automatically by `lint_cobol.py`.
Files must be named `Lxxx_description.py` and export:
- `RULE_ID` (str) — e.g. `"L001"`
- `SEVERITY` (str) — `"ERROR"`, `"WARNING"`, or `"INFO"`
- `DESCRIPTION` (str) — one-line summary
- `check(program_name: str, lines: list[str]) -> list[dict]` — returns findings

## Classification System

| Type | Name | Meaning | Safe to compile? | Action |
|---|---|---|---|---|
| **A** | Syntactic Workaround | Restructured syntax, identical semantics | ✅ Yes | Rewrite before analysis tool |
| **B** | Bug Fix | Corrects logic error in original source | ✅ Yes | Document defect, get sign-off |
| **C** | Tool Stub | Inserted for analysis tool compat only | ⚠️ Strip first | Remove before GnuCOBOL compile |
| **D** | Annotation | Comments only | ✅ Yes | Low risk |

## Current Rules

| Rule ID | Severity | Type | Trigger | Status |
|---|---|---|---|---|
| L001 | ERROR | A | `IF <bool-condition> AND <data> EQUAL` compound | ✅ Active |
| L002 | ERROR | A | `WHEN <bool-condition> AND <data> EQUAL` compound | ✅ Active |
| L003 | WARNING | C | Stub EXIT paragraph (only verb is EXIT) | ✅ Active |
| L004 | INFO | — | `PERFORM..THRU` (adjacency audit) | ✅ Active |

## How to Add a New Rule

1. Create `validation/lint_cobol/rules/Lxxx_short_name.py`
2. Set `RULE_ID`, `SEVERITY`, `DESCRIPTION` at module level
3. Implement `def check(program_name, lines) -> list[dict]:`
4. Each finding dict must have keys: `rule`, `severity`, `file`, `line`, `message`
5. Add an entry to this README table
6. Run `py -3 validation/lint_cobol/lint_cobol.py` to verify

## Why Lints, Not Fine-Tunes

Fine-tuning an LLM on COBOL source teaches it to reproduce the *surface form*
of the original programs, including any bugs and analysis-tool incompatibilities
already present in the corpus. It also requires labelled data that does not exist.

Lints solve the actual problem: they are **deterministic, auditable, zero-cost
to run**, and they produce a structured finding log that survives project handoffs.
Every rule in this catalogue corresponds to a documented failure mode observed
during the smojol-cli analysis phase. The lint corpus grows with observed failures
— fine-tuning would need to be retrained each time.
