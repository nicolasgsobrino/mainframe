---
schema_version: "aifirst/2.1"
task_id: "{{TASK_ID}}"
gate: G3
gate_name: "EXECUTE"
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
depends_on: ["{{TASK_ID}}/G2"]
override_reason: null
first_principles_revision: null
---

# G3 — EXECUTE

> **Gate purpose:** Fill the scaffold with content. Narrative,
> interpretations, goto_acceptance. NEVER modify frontmatter
> numbers — those are locked at G2. NEVER add files outside those
> declared in G1. Every non-trivial claim must cite the source
> `.cbl` line number.

---

## No-Edit Assertion

<!-- Confirm frontmatter numbers were NOT modified during G3.
     Copy values from G2 Frontmatter Verification and re-verify
     after content fill. -->

| field | G2-locked value | post-G3 value | unchanged |
|---|---|---|---|
| paragraphs_expected | | | |
| l01_items_expected | | | |
| reachable_expected | | | |
| dead_paragraphs_allowed | | | |
| source_sha | | | |
| cfg_sha | | | |

**Frontmatter integrity:** PENDING

---

## Evidence Sources Used

<!-- Every source file consulted during content fill.
     No claim may appear in the .md without a corresponding entry here. -->

| source | path | sha | sections_citing_this |
|---|---|---|---|
| COBOL source | app/cbl/{{PROGRAM_ID}}.cbl | | |
| CFG summary | validation/structure/{{PROGRAM_ID}}_cfg.json | | |
| Annotations | validation/waves/wave-1/{{PROGRAM_ID}}_annotations.json | | |

---

## Step Log

<!-- Each sub-step appended here AND to run.log as JSON-L event.
     step_id format: {{TASK_ID}}-G3-NNN -->

| step_id | description | status | timestamp | notes |
|---|---|---|---|---|
| {{TASK_ID}}-G3-001 | | PENDING | | |
| {{TASK_ID}}-G3-002 | | PENDING | | |

---

## Error Log

<!-- Any error encountered during execution.
     If ANY error appears here, gate status = FAIL → BLOCKED.
     Do NOT self-correct. Write BLOCKED and halt. -->

| step_id | error_type | message | action_taken |
|---|---|---|---|

---

## Claims Validation Pre-check

```text
Command: py validation/extract_md_claims.py {{PROGRAM_ID}}
Expected: [OK] status, no lint_warnings_in_claims,
          no hallucinated_paragraphs
```

| run | exit_code | status | lint_warnings | hallucinated_paragraphs | notes |
|---|---|---|---|---|---|
| | | PENDING | | | |

---

## Drift Notes

<!-- Any deviation from G1 scope observed during execution.
     If any new file was created beyond G1 manifest, document here.
     If scope changed, halt and re-open G0. -->

---

## G3 Pass Checklist

- [ ] All frontmatter numbers unchanged from G2 lock
- [ ] All claims cite `.cbl` line numbers
- [ ] No files created outside G1 manifest
- [ ] `extract_md_claims.py` → `[OK]`, zero hallucinated paragraphs
- [ ] Error log empty (or OVERRIDE with human-approved reason)
- [ ] No scope drift (or G0 re-opened)

**G3 Status:** PENDING
