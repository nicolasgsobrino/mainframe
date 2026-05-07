# G0 — DECOMPOSE

> **Gate purpose:** Reduce the problem to its irreducible unit before
> any planning begins. Reject symptom-level framings. This gate cannot
> pass with "I will investigate" — investigation is G2, not G0.

---

---
schema_version: "aifirst/2.1"
task_id: "T-2026-05-06-001"
gate: G0
gate_name: "DECOMPOSE"
status: PENDING
agent: "qwen3-coder-next-80b"
branch: "preserve/local-progress-2026-05-06"
branch_scope_sha: "4e43543844c5e6167e45c8d33624cc02ce2c6e23"
manifest_sha: "713063e34e48a15fc730121065a974e06f055349"
program_id: "CBACT04C"
locked_numbers_ref: null
timestamp_open: "2026-05-06T12:02:00Z"
timestamp_close: null
parent_task_id: null
depends_on: []
override_reason: null
first_principles_revision: null
---

## Q1 — Irreducible Unit of Work

**Answer:** CBACT04C.md gold candidate (one deliverable - the translated Markdown file with 1:1 COBOL logic mapping, gate N/N PASS via syncd)

---

## Q2 — Inputs

| Input | Path | SHA / version | Notes |
|---|---|---|---|
| COBOL source | app/cbl/CBACT04C.cbl | c5e0280e2ed0891877b43eda7bc7c6dc86752421 | Locked source SHA |
| CFG summary | validation/structure/CBACT04C_cfg.json | 7dfec5b5c5e7c8e968b79cc11c3a04831e8b381f | Locked CFG SHA |
| SYNC-MANIFEST | SYNC-MANIFEST.yaml | 713063e34e48a15fc730121065a974e06f055349 | Locked numbers source |
| BRANCH-SCOPE | BRANCH-SCOPE.md | 4e43543844c5e6167e45c8d33624cc02ce2c6e23 | Scope discipline rules |
| Protocol spec | .clinerules/00-aifirst-protocol.md | 7b118052ac10ffe1414a2c48877b277e6c35059c | Gate template schema |

---

## Q3 — Invariants

| Invariant | Expected value | Source |
|---|---|---|
| paragraphs_expected | 22 | SYNC-MANIFEST.yaml |
| l01_items_expected | 24 | SYNC-MANIFEST.yaml |
| reachable_expected | 22 | SYNC-MANIFEST.yaml |
| dead_paragraphs_allowed | 0 | SYNC-MANIFEST.yaml |
| source_sha | c5e0280e2ed0891877b43eda7bc7c6dc86752421 | SYNC-MANIFEST.yaml |
| cfg_sha | 7dfec5b5c5e7c8e968b79cc11c3a04831e8b381f | SYNC-MANIFEST.yaml |

---

## Q4 — Proof of Correctness

```text
Command: py tools/syncd/sync.py verify
Expected: exit 0, Gate: N/N PASS (current corpus count), Lint: 0 errors, Claims: [OK]
```

---

## Q5 — Proof of Failure

| Failure signature | Trigger condition |
|---|---|
| hallucinated_paragraphs in claims | Paragraph name not in CFG JSON |
| lint_warnings_in_claims | Structural claim violation |
| syncd verify exit non-zero | Any regression in corpus or CBACT04C failure |
| frontmatter number mismatch | Any field ≠ SYNC-MANIFEST.yaml value |
| truncation error | Paragraph name pattern starts with 9999- or 0100- etc. |

---

## Q6 — Explicit Out of Scope

- (cross-ref BRANCH-SCOPE.md SHA: 4e43543844c5e6167e45c8d33624cc02ce2c6e23)
- Any file under app/, translations/, demo/, scripts/ except CBACT04C.cbl
- SYNC-MANIFEST.yaml (no new locks during this task)
- Any file outside validation/structure/CBACT04C_cfg.json, translations/gold-candidate/CBACT04C.md, and .clinerules/runs/T-2026-05-06-001/
- Fixing pre-existing errors in other programs (CBACT01C-03C, CBSTM03A, CBSTM03B, CBTRN01C, etc.)

---

## Q7 — First-Principles Assumption That Could Be False

**Assumption:** The CFG JSON (validation/structure/CBACT04C_cfg.json) contains sufficient structural information to prevent LLM hallucinations for a 22-paragraph program.

**How to test it:** Run `py tools/syncd/sync.py verify` after G3 content fill. If any hallucinated_paragraphs are detected, the assumption is false.

**If false, re-decompose as:** CFG structural gap class — need to add missing structural fields (calls_to, called_by, copybooks_used, etc.) to the CFG extractor before LLM inference.

---

## G0 Pass Checklist

- [x] Q1: irreducible unit is one noun, one deliverable
- [x] Q2: all inputs listed with paths and SHAs
- [x] Q3: all invariants sourced from SYNC-MANIFEST.yaml
- [x] Q4: proof commands are copy-paste executable
- [x] Q5: failure signatures are unambiguous
- [x] Q6: out-of-scope list is enumerated, not "everything else"
- [x] Q7: assumption is testable and re-decomposition path is named
- [ ] Human ACK received if any risk_flag is non-empty

**G0 Status:** PENDING