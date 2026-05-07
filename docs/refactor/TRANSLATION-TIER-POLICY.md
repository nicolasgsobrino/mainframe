# Translation Tier Policy

> **Created:** 2026-05-05 | **Operation:** OPERATION-TIDY | **Step:** Commit D (OP-3-12)
> **Authority:** This document governs the `translations/` directory structure.
> All agents must read this policy before creating, modifying, or promoting translation files.

---

## Tier Definitions

| Tier | Path | Purpose | Mutability | Promotion Gate |
|---|---|---|---|---|
| `baseline` | `translations/baseline/` | v1.0 LLM-generated translations. Read-only historical reference. Captures pre-pipeline quality bar. | **Read-only** — never edit after initial commit | None — baseline is the starting point, not a destination |
| `gold-candidate` | `translations/gold-candidate/` | **Primary active tier.** All current pipeline work targets this tier. Schema-validated, gate-tested. | Mutable — only by pipeline with gate PASS | Gate PASS required: T01 (schema lint), T02 (YAML parse), T02-R (ground truth), T03 (semantic score ≥0.85) |
| `gold` | `translations/gold/` | Graduated tier. Programs that have passed all gates including T04 (human/judge review). | Append-only — once promoted, never demoted or edited | All T01–T04 gates PASS + human review |

### Tier Under Review (as of 2026-05-05)

| Path | Status | Decision |
|---|---|---|
| `translations/baseline-v1.2/` | **Archived** — moved to `archive/translations-baseline-v1.2/` in Commit B (OP-2-03). Was a 4th copy tier with no pipeline role. | Versioning via git tags only, not directory copies. |
| `translations/gold/` | **Active stub.** Contains only `COBSWAIT.md` (promoted 2026-04-27, commit `0bffc18`). | Tier is valid. Populate via promotion as programs clear T04. Do not add stub files manually. |

---

## Promotion Protocol

Promotion from `gold-candidate` to `gold` is a **deliberate, one-way action**.

```
1. Confirm all four gates PASS for the program:
   - T01: schema lint (lint_md.py) — 0 errors
   - T02: YAML frontmatter parse — all required fields present
   - T02-R: ground truth comparison (gate_compare.py) — all claims verified against CFG
   - T03: semantic score ≥ 0.85
   - T04: human or judge review — explicit approval by MrSnowNB

2. Copy file: `translations/gold-candidate/<PROG>.md` → `translations/gold/<PROG>.md`
   (Do NOT delete from gold-candidate — both tiers retain the file)

3. Append promotion event to `.clinerules/runs/<TASK_ID>/run.log`:
   type: gold_promotion
   program: <PROGRAM_ID>
   source_sha: <blob SHA of gold-candidate file>
   gate_summary: T01=PASS T02=PASS T02-R=PASS T03=<score> T04=PASS
   promoted_by: <operator>
   commit: <commit SHA>

4. Update FOUNDATION_TRACKER.md (docs/audit/FOUNDATION_TRACKER.md)
   to mark the program as Fully Trusted ✅.
```

---

## Anti-Patterns (Do Not Do)

| Anti-Pattern | Why Forbidden |
|---|---|
| Edit `translations/baseline/` files | Baseline is the pre-pipeline quality record. Editing it destroys the before/after comparison. |
| Create new versioned directory copies (e.g. `baseline-v1.3/`) | Git tags are the versioning mechanism. Directory copies bloat the repo and confuse the pipeline tier model. |
| Promote to `gold/` without T04 gate | The gold tier is the trust signal for downstream consumers. Unprompted promotions dilute trust. |
| Delete from `gold-candidate/` after promotion | Both tiers must retain the file. `gold/` is the graduation certificate; `gold-candidate/` remains the working copy. |
| Write manually to `gold/` without running promotion protocol | Bypasses run.log audit trail. |

---

## COBSWAIT Special Case

COBSWAIT.md exists in all three tiers (baseline, gold-candidate, gold). This is **intentional**:
- `translations/baseline/COBSWAIT.md` — original v1.0 (read-only reference)
- `translations/gold-candidate/COBSWAIT.md` — active pipeline copy (working copy)
- `translations/gold/COBSWAIT.md` — first promoted program (SHA `21e6845d`)

The three copies have diverged slightly (different sizes). This is acceptable. The gold copy
is authoritative for downstream consumers. The baseline copy is the historical reference.
Do not synchronize them.

---

## Relationship to FOUNDATION_TRACKER

The canonical program-level status table lives in `docs/audit/FOUNDATION_TRACKER.md`.
This policy document governs directory structure and promotion rules only.

| Document | Governs |
|---|---|
| `docs/refactor/TRANSLATION-TIER-POLICY.md` (this file) | Directory structure, tier definitions, promotion protocol |
| `docs/audit/FOUNDATION_TRACKER.md` | Per-program gate status, wave plan, scorecard |
| `docs/refactor/OPERATION-TIDY-PLAN.md` | Repo-wide restructuring plan (Steps 1–3) |

---

*Maintained by Operation Tidy. Last updated: 2026-05-05.*
