---
schema_version: "aifirst/2.1"
task_id: "{{TASK_ID}}"
gate: G5
gate_name: "COMMIT"
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
depends_on: ["{{TASK_ID}}/G4"]
override_reason: null
first_principles_revision: null
---

# G5 — COMMIT

> **Gate purpose:** Persist work atomically with full audit trail.
> Use `syncd bundle` to stage only the canonical file set — never
> `git add .`. Open a PR if branch is not `main`; solo-operator
> exception applies to `main` direct push.

---

## Pre-Commit Verification

- [ ] All five prior gates (G0–G4) status = PASS
- [ ] `run.log` integrity verified: append-only, no overwritten lines
- [ ] Branch matches G1 plan: `{{BRANCH}}`
- [ ] No uncommitted changes outside the G1 file manifest
- [ ] `syncd doctor` still exits 0 or 1 (no new errors since G4)

---

## syncd bundle

```text
Command: py tools/syncd/sync.py bundle {{PROGRAM_ID}} [--pr]
Expected: canonical file set staged; commit created with
          template: "feat(trust): {{PROGRAM_ID}} gold-candidate
                     — gate N/N PASS via syncd"
```

| step | command | exit_code | commit_sha | notes |
|---|---|---|---|---|
| bundle | | | | |

---

## Commit Record

```text
Commit SHA    : (fill after push)
Commit message: feat(trust): {{PROGRAM_ID}} gold-candidate — gate N/N PASS via syncd
task_id       : {{TASK_ID}}
branch        : {{BRANCH}}
pushed to     : origin/{{BRANCH}}
```

---

## run.log Completion Event

<!-- Append this event to run.log immediately after successful push. -->

```jsonc
{
  "event": "complete",
  "task_id": "{{TASK_ID}}",
  "gate": "G5",
  "program_id": "{{PROGRAM_ID}}",
  "commit_sha": "(fill)",
  "pr": "(fill or null if main)",
  "tag": "[AIFIRST-VERIFIED]",
  "ts": "{{NOW}}"
}
```

---

## Post-Mortem

### Planned (G0) vs. Built (G3)
<!-- "No drift" is a valid and good answer. -->

### Metrics Delta

| success_criterion | G0 target | G4 achieved | delta |
|---|---|---|---|
| SC-01 | | | |
| SC-02 | | | |
| SC-03 | | | |

### Lessons Learned
<!-- What would you change in G0 next time? -->

### Open Issues
<!-- Anything NOT resolved — each becomes a new task_id at G0 -->
- [ ]

---

## G5 Pass Checklist

- [ ] `syncd bundle` exited 0
- [ ] Commit SHA recorded
- [ ] `run.log` `complete` event appended
- [ ] PR opened (or solo-operator main-push documented)
- [ ] No files outside canonical set were committed

**G5 Status:** PENDING
