# AiFirst Protocol — Master Specification & Gate Templates
> **ARCHIVED** — This is the v1.0 protocol document, superseded by
> `.clinerules/00-aifirst-protocol.md` (v2.1+).
> Archived by Operation Tidy Step 2 on 2026-05-05.
> Original SHA: 3d93ef04708e61d4a37d230469d03dfd02b662e8

---

# AiFirst Protocol — Master Specification & Gate Templates

> **Repository:** [MrSnowNB/Morty](https://github.com/MrSnowNB/Morty)
> **Protocol Version:** `aifirst/1.0`
> **Date Authored:** 2026-04-23
> **Status:** DRAFT → ready for commit to `main`

***

## Overview

The `/aifirst` protocol is a **slash-command-driven, gate-validated execution standard** for all AI-assisted tasks in the Morty harness and downstream projects. Every task that invokes `/aifirst` must pass through five sequential gates before it is considered complete. Each gate has a corresponding Markdown file with a YAML front-matter header that the AI agent must populate in full before progression is allowed.

This protocol formalizes the existing patterns in the Morty repo — `AI-FIRST-IMPROVEMENT-PLAN.md`, `CHECKPOINT.md`, `POST-MORTEM.md`, and the `.claude/` command directory — into a single, repeatable, auditable system. It directly extends the `feat/ai-first-playbooks-and-validation-gates` branch work and the `task_id` propagation design.[^1]

***

## Design Principles

- **Gate-first execution** — no code runs before the plan is documented and optionally ACK'd
- **No simulated data** — validation tiers must use real outputs; mocked/synthetic data auto-fails G3
- **Append-only logging** — `run.log` is JSON-L; never overwrite, only append
- **Halt-on-failure** — any gate failure writes `BLOCKED` and stops; agents do not self-correct without re-entering G0
- **Traceability** — every file carries a `task_id`, every sub-step carries a `step_id`; both propagate into logs and PR titles[^1]
- **Human ACK on risk** — if `risk_flags` is non-empty in G0, a human must acknowledge before G1 opens

***

## Gate Flow

```
PLAN → SCAFFOLD → EXECUTE → VALIDATE → COMMIT
 G0       G1         G2         G3        G4
```

Each gate writes a `.md` file with a YAML header. The AI populates it. If the gate passes, status flips to `PASS` and the next gate opens. If it fails, status flips to `FAIL` → `BLOCKED` and the run halts.

***

## File Layout

All protocol files live inside `.claude/` in the Morty repo:

```
.claude/
  commands/
    aifirst.md                  ← slash command definition
  protocol/
    AIFIRST-SPEC.md             ← this document
    gates/
      G0-plan.template.md
      G1-scaffold.template.md
      G2-execute.template.md
      G3-validate.template.md
      G4-commit.template.md
  runs/
    <task_id>/
      G0-plan.md
      G1-scaffold.md
      G2-execute.md
      G3-validate.md
      G4-commit.md
      run.log                   ← append-only JSON-L
```

***

## YAML Header Schema

Every gate file uses this front-matter schema. All fields are required unless marked optional.

```yaml
---
schema_version: "aifirst/1.0"
task_id: "T-YYYY-MM-DD-NNN"       # e.g. T-2026-04-23-001
gate: G0                           # G0 | G1 | G2 | G3 | G4
gate_name: "PLAN"                  # PLAN | SCAFFOLD | EXECUTE | VALIDATE | COMMIT
status: PENDING                    # PENDING | PASS | FAIL | BLOCKED | OVERRIDE
agent: "model-name-here"           # exact model identifier used at this gate
timestamp_open: "ISO-8601"
timestamp_close: null              # filled on gate close
parent_task_id: null               # optional: for sub-tasks / escalations
depends_on: []                     # optional: task_ids that must PASS first
override_reason: null              # REQUIRED if status = OVERRIDE; null otherwise
---
```

**Rules:**
- `task_id` format is strictly `T-YYYY-MM-DD-NNN` with zero-padded three-digit sequence
- `status` must be one of the five enum values; any other string is a schema violation (T01 fail)
- `override_reason` must be a non-null string if and only if `status = OVERRIDE`
- `timestamp_close` must be populated before the gate can be marked `PASS`

***

## The Slash Command

**File:** `.claude/commands/aifirst.md`

```yaml
---
schema_version: "aifirst/1.0"
command: "/aifirst"
version: "1.0.0"
description: >
  Invoke the AiFirst gated validation protocol for a task.
  Creates a runs/<task_id>/ directory and opens G0-plan.md
  for population before any execution begins.
parameters:
  - name: task_name
    required: true
    type: string
    description: "Short human-readable label for the task"
  - name: tier_ceiling
    required: false
    default: T05
    type: "enum[T01,T02,T03,T04,T05]"
    description: "Highest validation tier to run in G3"
  - name: skip_human_ack
    required: false
    default: false
    type: boolean
    description: "Only valid when G0 risk_flags is empty"
behavior:
  on_invoke:
    - "Generate task_id using format T-YYYY-MM-DD-NNN"
    - "Create runs/<task_id>/ directory"
    - "Copy gate templates into runs/<task_id>/"
    - "Populate G0-plan.md YAML header and body"
    - "If risk_flags non-empty AND skip_human_ack=false: pause, surface to user, await ACK"
    - "On ACK: open G1"
  on_gate_fail:
    - "Write BLOCKED entry to run.log"
    - "Set gate status to FAIL"
    - "Surface error and blocked gate to user"
    - "Halt — do not proceed to next gate"
    - "Do not self-correct without re-entering G0"
  on_complete:
    - "Verify all five gates status = PASS"
    - "Write final POST-MORTEM block to G4-commit.md"
    - "Tag PR title with [AIFIRST-VERIFIED]"
    - "Append completion event to run.log"
---
```

***

## Gate Templates

***

### G0 — PLAN

**File:** `.claude/protocol/gates/G0-plan.template.md`

```yaml
---
schema_version: "aifirst/1.0"
task_id: "{{TASK_ID}}"
gate: G0
gate_name: "PLAN"
status: PENDING
agent: "{{AGENT}}"
timestamp_open: "{{NOW}}"
timestamp_close: null
parent_task_id: null
depends_on: []
override_reason: null
---
```

### G1 — SCAFFOLD through G4 — COMMIT

[Full template content preserved — see original commit SHA 3d93ef04708e61d4a37d230469d03dfd02b662e8]

***

## Version History

| Version | Date | Author | Notes |
|---------|------|--------|-------|
| 1.0.0 | 2026-04-23 | Mark Snow / Perplexity | Initial draft from Morty repo patterns |
