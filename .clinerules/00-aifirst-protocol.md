# AiFirst Protocol — Master Specification

> **Protocol Version:** `aifirst/2.2`
> **Status:** ACTIVE
> **Supersedes:** `aifirst/1.0`, `aifirst/2.0`, `aifirst/2.1`

## Overview

The `/aifirst` protocol is a **gate-validated, first-principles execution standard** for every AI-assisted task in this repo. Tasks progress through six sequential gates (G0–G5). Each gate has a templated Markdown file with a YAML header the agent must populate before advancing. Gates are backed by the `syncd` toolchain so validation is mechanical, not advisory.

This protocol enforces **first-principles problem solving loops** at G0 and G3 — agents decompose problems to their irreducible parts before writing code, and re-enter decomposition on any gate failure rather than patching symptoms.

## Design Principles

- **Gate-first execution** — no code runs before the plan is decomposed and documented.
- **First-principles decomposition** — every G0 must answer: *what is the irreducible unit of work, what are its inputs, what are its invariants, what would prove it correct?* Symptoms are never the unit of work.
- **Evidence over memory** — every claim must cite the exact command + output that proves it. No "as I recall" reasoning.
- **No simulated data** — validation uses real syncd + extractor output; mocked or synthetic data auto-fails G3.
- **Append-only logging** — `run.log` is append-only JSON-L. Never truncated.
- **Halt-on-failure with mandatory re-decomposition** — any gate failure writes `BLOCKED` and halts; the agent does not self-correct. Unblocking requires re-entering G0 (not G1 or G2) to re-decompose.
- **Traceability** — every file carries `task_id`; every sub-step carries `step_id`; both propagate into commit messages and PR titles.
- **Scope respect** — every gate honors `BRANCH-SCOPE.md` and `SYNC-MANIFEST.yaml`. Out-of-scope edits auto-fail G1.
- **Locked-number invariance** — any `.md` whose frontmatter numbers disagree with `SYNC-MANIFEST.yaml.locked_numbers` auto-fails G3.

## Gate Flow

```text
DECOMPOSE → PLAN → SCAFFOLD → EXECUTE → VALIDATE → COMMIT
   G0        G1      G2         G3        G4         G5
```

**G0 is new in v2.0** and is non-optional. It is the first-principles loop entry point.

Each gate writes a `.md` file with a YAML header. The AI populates it. If the gate passes, status flips to `PASS` and the next gate opens. If it fails, status flips to `FAIL` → `BLOCKED` and the run halts. Resuming requires creating a new `task_id` that starts at G0 with `parent_task_id` pointing at the blocked task.

## Gate Definitions

### G0 — DECOMPOSE (first-principles loop)

**Purpose:** Reduce the problem to irreducible units before planning. Reject symptom-level framings.

**Agent must answer, in the gate file:**
1. **What is the irreducible unit of work?** (one noun, one deliverable)
2. **What are its inputs?** (files, data, locked numbers, prior gate output)
3. **What are its invariants?** (counts, SHAs, baselines that must not change)
4. **What would prove it correct?** (exact commands + expected outputs)
5. **What would prove it wrong?** (failure signatures that trigger halt)
6. **What is explicitly out of scope?** (cross-reference `BRANCH-SCOPE.md`)
7. **What first-principles assumption could be false?** (what would force re-decomposition)

**PASS criteria:** All 7 questions answered with concrete artifacts, not hand-waving. G0 cannot pass with "I will investigate" — investigation is G2, not G0.

### G1 — PLAN

**Purpose:** Translate G0's irreducible unit into a concrete action sequence.

**Agent must produce:**
- Ordered list of steps (each with `step_id`)
- Exact commands to run per step
- Files to read (inputs) and files to write (outputs)
- Gate-pass criteria for each step
- Rollback procedure for each step
- Locked-number snapshot from `SYNC-MANIFEST.yaml`

**PASS criteria:** Plan survives the "can a different agent execute this verbatim?" test. No discretionary language ("as appropriate", "if needed").

### G2 — SCAFFOLD

**Purpose:** Produce empty structure before filling it. For `.md` deliverables, this means running `syncd scaffold <PROG>` to generate frontmatter + stubs from locked numbers.

**Agent must:**
- Run `syncd doctor` — must exit 0 or 1 (warnings only)
- Run `syncd scaffold <PROG> --force` (if .md does not yet exist)
- Verify scaffold frontmatter matches `SYNC-MANIFEST.yaml.locked_numbers` for program
- Commit scaffolded skeleton separately (not mixed with G3 fills)

**PASS criteria:** Skeleton file exists with correct frontmatter, no narrative content yet. Exit codes recorded.

### G3 — EXECUTE

**Purpose:** Fill the scaffold with content. Narrative, interpretations, goto_acceptance.

**Agent must:**
- Never modify frontmatter numbers (those are locked at G2)
- Never add files outside those declared in G1
- Use only evidence from committed sources (CFG JSON, GT JSON, .cbl source)
- Cite line numbers in .cbl source for every non-trivial claim

**PASS criteria:** `.md` passes `py validation/extract_md_claims.py <PROG>` with `[OK]` status. No `lint_warnings_in_claims`. No `hallucinated_paragraphs`.

### G4 — VALIDATE

**Purpose:** Mechanical verification via the syncd toolchain.

**Agent must run, in order:**

```text
py tools/syncd/sync.py verify
```

which internally runs `gate_compare.py`, `lint_cobol.py`, `extract_md_claims.py`.

**PASS criteria:**
- Gate: N/N PASS (current corpus count, no regressions)
- Lint: 62 files / 0 errors / 2 warnings (or current baseline)
- Claims: `[OK]` with `t04=NULL` on new entry
- Exit code 0

**On FAIL:** Write `BLOCKED`, halt, require new `task_id` at G0.

### G5 — COMMIT

**Purpose:** Persist work atomically with full audit trail.

**Agent must:**
- Run `syncd bundle <PROG>` (which stages only canonical file set)
- Commit with template: `feat(trust): <PROG> gold-candidate — gate N/N PASS via syncd`
- Include `task_id` in commit body
- Push to current branch (respecting `BRANCH-SCOPE.md` branch-type rules)
- Open PR only if branch is not `main` (solo-operator exception applies to `main`)

**PASS criteria:** Commit SHA recorded, `run.log` event `complete` written.

## First-Principles Failure Loop

On any gate failure, the agent **must not** patch forward. The required loop is:

```text
FAIL at Gn → write BLOCKED → halt
              ↓
            new task_id T-YYYY-MM-DD-NNN+1 with parent_task_id pointing at blocked task
              ↓
            re-enter G0 with new framing
              ↓
            G0 question 7: "what first-principles assumption was false?"
              ↓
            proceed only when G0 answers 1–7 with revised understanding
```

This enforces that root causes are diagnosed once, at G0 re-entry, rather than drifting through patches at G2/G3. The "truncation bug" class of failures (where symptoms appear in extractor output) must be re-decomposed at G0, not fixed at G2.

## File Layout

```text
.clinerules/
  00-aifirst-protocol.md              ← this document
  01-scope-discipline.md              ← BRANCH-SCOPE.md enforcement rules
  02-cobol-to-md.md                   ← translation rules
  protocol/
    gates/
      G0-decompose.template.md        ← first-principles decomposition
      G1-plan.template.md             ← action sequence + locked numbers
      G2-scaffold.template.md         ← syncd scaffold + frontmatter lock
      G3-execute.template.md          ← content fill + evidence log
      G4-validate.template.md         ← syncd verify + regression check
      G5-commit.template.md           ← syncd bundle + run.log complete
  runs/
    <task_id>/
      G0-decompose.md
      G1-plan.md
      G2-scaffold.md
      G3-execute.md
      G4-validate.md
      G5-commit.md
      run.log                         ← append-only JSON-L
```

## YAML Header Schema

```yaml
---
schema_version: "aifirst/2.1"
task_id: "T-YYYY-MM-DD-NNN"        # e.g. T-2026-05-04-003
gate: G0                            # G0 | G1 | G2 | G3 | G4 | G5
gate_name: "DECOMPOSE"              # DECOMPOSE | PLAN | SCAFFOLD | EXECUTE | VALIDATE | COMMIT
status: PENDING                     # PENDING | PASS | FAIL | BLOCKED | OVERRIDE
agent: "model-name-here"            # exact model identifier used at this gate
branch: "wave1/cbstm03a"            # required — current git branch
branch_scope_sha: "abc1234"         # required — SHA of BRANCH-SCOPE.md at gate open
manifest_sha: "def5678"             # required — SHA of SYNC-MANIFEST.yaml at gate open
program_id: "CBSTM03A"              # required for any program-scoped task
locked_numbers_ref: "CBSTM03A"      # key into SYNC-MANIFEST.yaml.locked_numbers
timestamp_open: "ISO-8601"
timestamp_close: null               # filled on gate close
parent_task_id: null                # required if this task was spawned from a BLOCKED task
depends_on: []                      # optional: task_ids that must PASS first
override_reason: null               # REQUIRED if status = OVERRIDE; null otherwise
first_principles_revision: null     # required on G0 re-entry after BLOCKED
---
```

**New v2.0 rules:**
- `branch_scope_sha` and `manifest_sha` are required. They pin the scope context at gate open so later-merged changes don't invalidate the gate decision.
- `program_id` is required for any task touching a `.cbl`, `.md`, or `_cfg.json`.
- `first_principles_revision` must be populated on G0 for any task with a non-null `parent_task_id` — captures what assumption was revised.
- `status = OVERRIDE` requires `override_reason` AND human approval recorded in `run.log`.

## run.log Schema (v2.0 additions)

```jsonc
// Gate open — v2.0 adds branch + manifest SHAs
{"event":"gate_open","task_id":"T-2026-05-04-003","gate":"G0","agent":"claude-sonnet-4.6","branch":"wave1/cbstm03a","branch_scope_sha":"abc1234","manifest_sha":"def5678","ts":"2026-05-04T21:58:00Z"}

// First-principles decomposition event (new in v2.0)
{"event":"decompose","task_id":"T-2026-05-04-003","gate":"G0","irreducible_unit":"CBSTM03A.md gold candidate","inputs":["CBSTM03A_cfg.json","SYNC-MANIFEST.yaml","CBSTM03A.cbl"],"invariants":{"paragraphs":25,"l01_items":18},"ts":"2026-05-04T21:58:30Z"}

// Scope-violation event (new in v2.0) — auto-written when forbidden path touched
{"event":"scope_violation","task_id":"T-2026-05-04-003","gate":"G2","attempted_path":"validation/extract_cfg_summary.py","ts":"2026-05-04T22:01:00Z"}

// Syncd integration event (new in v2.0)
{"event":"syncd","task_id":"T-2026-05-04-003","gate":"G4","command":"verify","exit_code":0,"ts":"2026-05-04T22:10:00Z"}

// Halt + re-entry pointer (new in v2.0)
{"event":"blocked","task_id":"T-2026-05-04-003","gate":"G3","reason":"hallucinated_paragraphs: ['END-PERFORM']","next_task_id":"T-2026-05-04-004","ts":"2026-05-04T22:15:00Z"}

// First-principles re-entry (new in v2.0)
{"event":"first_principles_revision","task_id":"T-2026-05-04-004","parent_task_id":"T-2026-05-04-003","revision":"Scope-terminator tokens are not paragraph names; must exclude END-PERFORM class from .md paragraph list","ts":"2026-05-04T22:16:00Z"}

// Completion
{"event":"complete","task_id":"T-2026-05-04-004","pr":"https://github.com/.../pull/47","tag":"[AIFIRST-VERIFIED]","ts":"2026-05-04T22:30:00Z"}

// Correction event (v2.1) — fixes a field value in a prior gate file
// Appended to run.log, never overwrites prior lines
{"event":"correction","task_id":"...","field":"<field_name>","scope":"<where>","incorrect_value":"...","correct_value":"...","correction_ts":"...","reason":"...","corrected_by":"human"}
```

## Derivation Discipline (v2.1 addition)

Every YAML field must have exactly one authoritative source. Agents must
NEVER copy field values from adjacent context. Specific rules:

### `agent:` field
Derive from one of these, in order:
1. Environment variable `CLINE_MODEL` if set
2. Cline runtime model configuration visible in the Cline panel
3. If uncertain, halt and ask the human — do NOT guess

Forbidden sources:
- Other `.md` file frontmatter (e.g., `translating_agent` in gold-candidate `.md`s)
- Example YAML in protocol documentation or kickoff prompts
- Prior task_id `run.log` events

Valid format: `<family>-<variant>[-<tag>]` (e.g., `qwen3-coder-next-80b`,
`claude-sonnet-4.6`, `gpt-5-thinking`). Vague strings like `"cloud"`, `"local"`,
or `"cline-agent"` are schema violations.

### `parent_task_id:` field
Populated ONLY when this task was spawned from a different task that
reached `BLOCKED` status. Must point to that different task's `task_id`.
- If this is a fresh task: `null`
- If this is a gate continuation within the same task: `null`
- Self-reference (`parent_task_id == task_id`) is a schema violation

### `locked_numbers_ref:` field
- `null` until `syncd lock` has been run for this task's `program_id`
- After lock: the `program_id` string (e.g., `"CBCUS01C"`)
- Must never be populated from another program's locked numbers

### General derivation rule
When populating any field, the agent must be able to cite the exact
source file and line from which the value was derived. If the source
cannot be cited, the value is not yet known — halt and ask the human.

## Correspondence to syncd Toolchain

| AiFirst Gate | syncd Command | Enforcement |
|---|---|---|
| G0 DECOMPOSE | *(human + LLM)* | No tool; human reviews 7 questions |
| G1 PLAN | `syncd status`, `syncd doctor` | Manifest + branch state pinned |
| G2 SCAFFOLD | `syncd scaffold <PROG>` | Frontmatter locked from manifest |
| G3 EXECUTE | *(human + LLM)* | Narrative fill, no number edits |
| G4 VALIDATE | `syncd verify` | Gate + lint + claims mechanical |
| G5 COMMIT | `syncd bundle <PROG> [--pr]` | Canonical file set only |

## Override Policy

Overrides exist for single, enumerated exceptions (source-SHA drift due to cross-merge, for example). Every override:
- Requires `override_reason` ≥ 1 sentence citing the specific exception class
- Requires a human-authored `run.log` entry: `{"event":"override_approved","approver":"<name>","ts":"..."}`
- Cannot be applied to G0, G4, or G5 — those are machine-verifiable by construction
- Is reviewed post-hoc; three overrides on a single task_id chain trigger protocol revision

## Migration from v1.0

v1.0 tasks already PASSed are grandfathered as `schema_version: aifirst/1.0` in their gate files. No retroactive re-validation required. New tasks starting after protocol v2.0 activation use `aifirst/2.0` and include G0.

Recommended transition: run the next wave program (CBACT04C or CBCUS01C new trust-grade pass) entirely through v2.0 as a proof point before requiring v2.0 for all tasks.

## v2.2 Changelog

**Version:** `aifirst/2.2` | **Date:** 2026-05-05 | **Operation Tidy Commit F-1**

### Template Reconciliation (breaking fix)

Prior to v2.2, the gate template files under `.clinerules/protocol/gates/`
were authored for the **v1.0 5-gate model** (G0=PLAN, G1=SCAFFOLD,
G2=EXECUTE, G3=VALIDATE, G4=COMMIT) and never updated when the protocol
evolved to the **v2.x 6-gate model** (G0=DECOMPOSE, G1=PLAN, G2=SCAFFOLD,
G3=EXECUTE, G4=VALIDATE, G5=COMMIT).

This caused every fresh-agent session loading v2.1 to look for
`G0-decompose.template.md` and find nothing — a silent failure mode
that caused agents to hallucinate gate structure or fall back to the
wrong v1.0 template.

**Changes in v2.2:**

| Old file (deleted) | `gate_name` | New file (created) | `gate_name` |
|---|---|---|---|
| `G0-plan.template.md` | PLAN | `G1-plan.template.md` | PLAN |
| `G1-scaffold.template.md` | SCAFFOLD | `G2-scaffold.template.md` | SCAFFOLD |
| `G2-execute.template.md` | EXECUTE | `G3-execute.template.md` | EXECUTE |
| `G3-validate.template.md` | VALIDATE | `G4-validate.template.md` | VALIDATE |
| `G4-commit.template.md` | COMMIT | `G5-commit.template.md` | COMMIT |
| *(absent)* | — | `G0-decompose.template.md` | DECOMPOSE |

All new templates carry `schema_version: aifirst/2.1` and include
v2.1-required fields (`branch`, `branch_scope_sha`, `manifest_sha`,
`program_id`, `first_principles_revision`).

Section structures were ported from v1.0 templates where applicable.
`G0-decompose.template.md` was authored fresh from the v2.1 spec's
DECOMPOSE definition (the 7 first-principles questions).

### Schema Version vs Protocol Version

The gate YAML headers continue to carry `schema_version: aifirst/2.1`
after this release. The v2.2 bump applies to `00-aifirst-protocol.md`
only (the protocol document). Gate schema is unchanged; only the
template file set was reconciled. The YAML Header Schema example
above continues to show `aifirst/2.1` for that reason.

### No behavioral changes to gate definitions

Gate definitions (G0–G5), the failure loop, derivation discipline,
override policy, and syncd toolchain correspondence are unchanged
from v2.1. This release is a template artifact fix only.
