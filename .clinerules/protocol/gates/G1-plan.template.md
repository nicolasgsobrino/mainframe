---
schema_version: "aifirst/2.1"
task_id: "{{TASK_ID}}"
gate: G1
gate_name: "PLAN"
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
depends_on: ["{{TASK_ID}}/G0"]
override_reason: null
first_principles_revision: null
---

# G1 — PLAN

> **Gate purpose:** Translate G0's irreducible unit into a concrete,
> verbatim-executable action sequence. No discretionary language
> ("as appropriate", "if needed"). A different agent must be able
> to execute this plan without asking any clarifying questions.

---

## Locked-Number Snapshot

<!-- Copy from SYNC-MANIFEST.yaml at manifest_sha above.
     These values are frozen for this task. Any .md frontmatter
     that disagrees with these numbers auto-fails G4. -->

```yaml
# From SYNC-MANIFEST.yaml @ {{MANIFEST_SHA}}
program_id: "{{PROGRAM_ID}}"
paragraphs_expected:
l01_items_expected:
reachable_expected:
dead_paragraphs_allowed:
source_sha:
cfg_sha:
```

---

## Action Sequence

<!-- Ordered list. Each step has a step_id, exact command(s),
     input file(s), output file(s), pass criterion, and rollback.
     No step may say "investigate" or "check as needed". -->

| step_id | description | command(s) | inputs | outputs | pass criterion | rollback |
|---|---|---|---|---|---|---|
| {{TASK_ID}}-S-001 | | | | | | |
| {{TASK_ID}}-S-002 | | | | | | |
| {{TASK_ID}}-S-003 | | | | | | |

---

## File Manifest

<!-- Every file that will be created, modified, or deleted.
     SHA required for all modified/deleted files (for rollback).
     New files: sha = null. -->

| Action | Path | Current SHA | Notes |
|---|---|---|---|
| CREATE | | null | |
| MODIFY | | | |

---

## Branch

```text
branch: {{BRANCH}}
```

---

## Risk Flags

<!-- If non-empty, human ACK required before G2 opens. -->

| flag | mitigation |
|---|---|
| | |

---

## G1 Pass Checklist

- [ ] All steps have exact commands (no "run as needed")
- [ ] All modified/deleted files have current SHAs recorded
- [ ] Locked numbers copied verbatim from SYNC-MANIFEST.yaml
- [ ] Plan survives "different agent, verbatim" test
- [ ] Risk flags acknowledged by human (if any)

**G1 Status:** PENDING
