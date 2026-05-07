---
schema_version: "aifirst/2.1"
task_id: "{{TASK_ID}}"
gate: G2
gate_name: "SCAFFOLD"
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
depends_on: ["{{TASK_ID}}/G1"]
override_reason: null
first_principles_revision: null
---

# G2 — SCAFFOLD

> **Gate purpose:** Produce empty structure before filling it.
> For `.md` deliverables: run `syncd scaffold` to generate
> frontmatter + stubs from locked numbers. Commit the skeleton
> SEPARATELY — never mix scaffold and G3 narrative content in
> the same commit.

---

## Pre-Scaffold Checks

### syncd doctor

```text
Command: py tools/syncd/sync.py doctor
Expected: exit 0 (or exit 1 with warnings only — no errors)
```

| check | result | exit_code | notes |
|---|---|---|---|
| syncd doctor | PENDING | | |

---

## Scaffold Execution

```text
Command: py tools/syncd/sync.py scaffold {{PROGRAM_ID}} [--force]
Expected: skeleton .md created with frontmatter from SYNC-MANIFEST
```

| step | command | exit_code | output_path | notes |
|---|---|---|---|---|
| scaffold | | | | |

---

## Frontmatter Verification

<!-- After scaffold, confirm every locked number in the generated
     frontmatter matches SYNC-MANIFEST.yaml exactly.
     Copy expected values from G1 Locked-Number Snapshot. -->

| field | expected (from manifest) | actual (from scaffolded file) | match |
|---|---|---|---|
| paragraphs_expected | | | |
| l01_items_expected | | | |
| reachable_expected | | | |
| dead_paragraphs_allowed | | | |
| source_sha | | | |
| cfg_sha | | | |

**Frontmatter match:** PENDING

---

## Stub Content Verification

<!-- Confirm skeleton exists with correct structure and NO
     narrative content yet. Stubs only. -->

- [ ] Skeleton file exists at expected path
- [ ] All section headings present (no missing stubs)
- [ ] No narrative content in any section (stubs only)
- [ ] No placeholder tokens from G1 remaining ({{TASK_ID}} etc.)

---

## Scaffold Commit

<!-- Record the commit SHA after pushing the skeleton. -->

```text
Scaffold commit SHA: (fill after push)
Scaffold commit message: "scaffold({{PROGRAM_ID}}): G2 skeleton — frontmatter locked from SYNC-MANIFEST"
```

---

## Drift Notes

<!-- Any deviation from G1 File Manifest observed during scaffolding.
     If scope has changed, re-open G0 before proceeding to G3. -->

---

## G2 Pass Checklist

- [ ] syncd doctor exit 0 or 1 (warnings only)
- [ ] syncd scaffold executed without error
- [ ] All frontmatter numbers match SYNC-MANIFEST.yaml exactly
- [ ] Skeleton committed separately (not mixed with G3 content)
- [ ] No scope drift (or G0 re-opened)

**G2 Status:** PENDING
