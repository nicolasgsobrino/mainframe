---
schema_version: "aifirst/2.1"
task_id: "{{TASK_ID}}"
gate: G4
gate_name: "VALIDATE"
status: PENDING
agent: "{{AGENT}}"
branch: "{{BRANCH}}"
branch_scope_sha: "{{BRANCH_SCOPE_SHA}}"
manifest_sha: "{{MANIFEST_SHA}}"
program_id: "{{PROGRAM_ID}}"
locked_numbers_ref: "{{PROGRAM_ID}}"
timestamp_open: "{{NOW}}"
timestamp_close: null
parent_task_id: null
depends_on: ["{{TASK_ID}}/G3"]
override_reason: null
first_principles_revision: null
---

# G4 — VALIDATE

> **Gate purpose:** Mechanical verification via the syncd toolchain.
> No human judgment substitutes for tool output here. If `syncd verify`
> exits non-zero, status = FAIL → BLOCKED. Do NOT patch forward.
> Unblocking requires a new task_id starting at G0.

---

## syncd verify

```text
Command: py tools/syncd/sync.py verify
Expected: exit 0
          Gate:  N/N PASS (no regressions)
          Lint:  62 files / 0 errors / 2 warnings (or current baseline)
          Claims: [OK] with t04=NULL on new entry
```

### Full Output

```text
(paste full stdout here)
```

### Result Summary

| check | expected | actual | pass |
|---|---|---|---|
| exit_code | 0 | | |
| gate_pass_count | N/N | | |
| lint_errors | 0 | | |
| lint_warnings | ≤baseline | | |
| claims_status | [OK] | | |
| t04_new_entry | NULL | | |

**syncd verify result:** PENDING

---

## Regression Check

<!-- Confirm no prior-passing program regressed.
     List any programs whose status changed from PASS to anything else. -->

| program | prior status | current status | regressed |
|---|---|---|---|
| (none expected) | | | |

**Regression check:** PENDING

---

## Locked-Number Invariance

<!-- Confirm the delivered .md frontmatter numbers match
     SYNC-MANIFEST.yaml exactly. Auto-fail if any mismatch. -->

| field | manifest value | .md frontmatter value | match |
|---|---|---|---|
| paragraphs_expected | | | |
| l01_items_expected | | | |
| reachable_expected | | | |
| dead_paragraphs_allowed | | | |
| source_sha | | | |
| cfg_sha | | | |

**Locked-number invariance:** PENDING

---

## On FAIL Protocol

```text
If any check above = FAIL:
  1. Set gate status = FAIL → BLOCKED
  2. Append to run.log: {"event":"blocked","gate":"G4",...}
  3. Do NOT attempt to fix inline
  4. Create new task_id T-YYYY-MM-DD-NNN+1
  5. Set parent_task_id = this task_id
  6. Re-enter G0, answer Q7: what first-principles assumption was false?
```

---

## G4 Pass Checklist

- [ ] `syncd verify` exit 0
- [ ] Gate count: N/N PASS (no regressions)
- [ ] Lint: 0 errors
- [ ] Claims: [OK], zero hallucinated paragraphs
- [ ] Locked numbers match manifest exactly
- [ ] No programs regressed

**G4 Status:** PENDING
