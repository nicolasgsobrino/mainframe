---
schema_version: "aifirst/2.1"
task_id: "{{TASK_ID}}"
gate: G0
gate_name: "DECOMPOSE"
status: PENDING
agent: "{{AGENT}}"
branch: "{{BRANCH}}"
branch_scope_sha: "{{BRANCH_SCOPE_SHA}}"
manifest_sha: "{{MANIFEST_SHA}}"
program_id: "{{PROGRAM_ID}}"
locked_numbers_ref: null
timestamp_open: "{{NOW}}"
timestamp_close: null
parent_task_id: null
depends_on: []
override_reason: null
first_principles_revision: null
---

# G0 — DECOMPOSE

> **Gate purpose:** Reduce the problem to its irreducible unit before
> any planning begins. Reject symptom-level framings. This gate cannot
> pass with "I will investigate" — investigation is G2, not G0.

---

## Q1 — Irreducible Unit of Work

<!-- One noun, one deliverable. E.g.: "CBSTM03A.md gold candidate"
     NOT "fix the translation" or "improve the pipeline". -->

**Answer:**

---

## Q2 — Inputs

<!-- Every file, dataset, locked number, or prior gate output this
     task depends on. Include exact path and SHA where known.
     Do NOT write "as needed" — list them all. -->

| Input | Path | SHA / version | Notes |
|---|---|---|---|
| | | | |

---

## Q3 — Invariants

<!-- Counts, SHAs, or baselines that MUST NOT change during this task.
     These become the G4 regression baseline.
     Source each from SYNC-MANIFEST.yaml or a prior verified commit. -->

| Invariant | Expected value | Source |
|---|---|---|
| | | |

---

## Q4 — Proof of Correctness

<!-- Exact commands + expected outputs that would prove this task
     succeeded. Must be mechanically verifiable, not advisory.
     E.g.: "py tools/syncd/sync.py verify → exit 0, N/N PASS" -->

```text
Command:
Expected output:
```

---

## Q5 — Proof of Failure

<!-- Exact failure signatures that trigger an immediate HALT.
     Must be specific enough that a different agent would
     recognize them without judgment. -->

| Failure signature | Trigger condition |
|---|---|
| | |

---

## Q6 — Explicit Out of Scope

<!-- Cross-reference BRANCH-SCOPE.md. List paths, files, or
     behaviors that are FORBIDDEN for this task_id.
     "Everything else" is not acceptable — be enumerated. -->

- (cross-ref BRANCH-SCOPE.md SHA: {{BRANCH_SCOPE_SHA}})

---

## Q7 — First-Principles Assumption That Could Be False

<!-- What single assumption, if wrong, would force re-decomposition
     from scratch? This is the re-entry point if G3 returns BLOCKED.
     Must be a testable claim, not a vague concern. -->

**Assumption:**

**How to test it:**

**If false, re-decompose as:**

---

## G0 Pass Checklist

- [ ] Q1: irreducible unit is one noun, one deliverable
- [ ] Q2: all inputs listed with paths and SHAs
- [ ] Q3: all invariants sourced from SYNC-MANIFEST.yaml
- [ ] Q4: proof commands are copy-paste executable
- [ ] Q5: failure signatures are unambiguous
- [ ] Q6: out-of-scope list is enumerated, not "everything else"
- [ ] Q7: assumption is testable and re-decomposition path is named
- [ ] Human ACK received if any risk_flag is non-empty

**G0 Status:** PENDING
