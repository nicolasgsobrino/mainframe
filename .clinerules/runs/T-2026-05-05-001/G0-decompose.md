# G0 — DECOMPOSE

> **Gate purpose:** Reduce the problem to its irreducible unit before
> any planning begins. Reject symptom-level framings. This gate cannot
> pass with "I will investigate" — investigation is G2, not G0.

---

---
schema_version: "aifirst/2.1"
task_id: "T-2026-05-05-001"
gate: G0
gate_name: "DECOMPOSE"
status: PASS
agent: "qwen3-coder-next-80b"
branch: "main"
branch_scope_sha: "4e43543844c5e6167e45c8d33624cc02ce2c6e23"
manifest_sha: "facee5d1e589d2d112f19e8c73b2cc3497320a79"
program_id: "CBCUS01C"
locked_numbers_ref: "CBCUS01C"
timestamp_open: "2026-05-05T17:38:00Z"
timestamp_close: "2026-05-05T17:44:00Z"
parent_task_id: null
depends_on: []
override_reason: null
first_principles_revision: null

## Q1 — Irreducible Unit of Work

**Answer:** CBCUS01C.md gold candidate (trust-grade, gate N/N PASS via syncd)

---

## Q2 — Inputs

| Input              | Path                                              | SHA                                      |
|---|---|---|---|
| COBOL source       | app/cbl/CBCUS01C.cbl                              | e30e6e15014e0341f7e399d427e63350ed5cc993 |
| CFG summary        | validation/structure/CBCUS01C_cfg.json            | d9f83aea2d118b8869b70eea5f7ce0287c4fe4e5 |
| SYNC-MANIFEST      | SYNC-MANIFEST.yaml                                | facee5d1e589d2d112f19e8c73b2cc3497320a79 |
| BRANCH-SCOPE       | BRANCH-SCOPE.md                                   | 4e43543844c5e6167e45c8d33624cc02ce2c6e23 |
| Protocol spec      | .clinerules/00-aifirst-protocol.md                | e1c1f2bacf932358c187d55fb31de0be38f5da05 |

---

## Q3 — Invariants

| Invariant               | Expected | Source         |
|---|---|---|
| paragraphs_expected     | 5        | SYNC-MANIFEST  |
| l01_items_expected      | 10       | SYNC-MANIFEST  |
| reachable_expected      | 5        | SYNC-MANIFEST  |
| dead_paragraphs_allowed | 0        | SYNC-MANIFEST  |
| source_sha              | e30e6e15014e0341f7e399d427e63350ed5cc993 | SYNC-MANIFEST |
| cfg_sha                 | d9f83aea2d118b8869b70eea5f7ce0287c4fe4e5 | SYNC-MANIFEST |

---

## Q4 — Proof of Correctness

```text
Command: py tools/syncd/sync.py verify
Expected: exit 0, Gate: N/N PASS, Lint: 0 errors, Claims: [OK]
```

---

## Q5 — Proof of Failure

| Signature                              | Trigger                              |
|---|---|
| hallucinated_paragraphs in claims      | paragraph name not in CFG            |
| lint_warnings_in_claims                | structural claim violation           |
| syncd verify exit non-zero             | any regression in corpus             |
| frontmatter number mismatch            | any field ≠ SYNC-MANIFEST value      |

---

## Q6 — Explicit Out of Scope

- Any file under app/, translations/, demo/, scripts/
- SYNC-MANIFEST.yaml (no new locks during proof-point)
- Any file outside validation/waves/wave-1/CBCUS01C* and
  .clinerules/runs/T-2026-05-05-001/

---

## Q7 — First-Principles Assumption That Could Be False

**Assumption:** The new v2.2 gate templates load correctly and the
              6-gate flow executes end-to-end without structural gaps.

**How to test:** Complete G0→G5 using only the new templates and
               observe whether syncd verify exits 0.

**If false, re-decompose as:** template defect class identified at
               gate Gn — new task_id to patch the specific template
               with parent_task_id = T-2026-05-05-001.

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

**G0 Status:** PASS
