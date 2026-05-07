---
schema_version: "aifirst/2.0"
task_id: "T-2026-05-04-001"
gate: G0
gate_name: "DECOMPOSE"
status: PENDING
agent: "qwen3-coder-next-80b"
branch: "main"
branch_scope_sha: "4e43543844c5e6167e45c8d33624cc02ce2c6e23"
manifest_sha: "78ef9b8bb11286416c9b612e3644f06f560ddef0"
program_id: "CBCUS01C"
locked_numbers_ref: null
timestamp_open: "2026-05-05T02:30:00Z"
timestamp_close: null
parent_task_id: null
depends_on: []
override_reason: null
first_principles_revision: null
---

## Objective

Promote CBCUS01C to gold-candidate trust grade by completing the full AiFirst v2.0 protocol gates (G0-G5) using the syncd toolchain.

## Scope

This task includes:
- G0: Decompose the problem of promoting CBCUS01C to gold-candidate trust grade
- G1: Create a concrete action plan for the promotion
- G2: Scaffolding the CBCUS01C.md file with correct frontmatter
- G3: Execute the narrative content fill for CBCUS01C.md
- G4: Validate using syncd verify command
- G5: Commit the work with full audit trail

Out-of-scope for this task:
- Fixing pre-existing errors in other programs (CBACT01C, CBACT02C, CBACT03C, CBACT04C, CBSTM03A, CBSTM03B, CBTRN01C, etc.)
- Modifying validation/ structure files for programs other than CBCUS01C
- Running any batch dispatches or LLM runs

## Success Criteria

- [ ] SC-01: CBCUS01C.md exists in translations/gold-candidate/ with correct YAML frontmatter
- [ ] SC-02: CBCUS01C_cfg.json exists in validation/structure/ with correct structure
- [ ] SC-03: `py validation/extract_md_claims.py CBCUS01C` returns [OK] status
- [ ] SC-04: `py tools/syncd/sync.py verify` exits 0 with CBCUS01C PASS
- [ ] SC-05: Commit made with SHA recorded in run.log

## Risk Flags

risk_flags:
  - flag: "Pre-existing truncation errors in other CFG files"
    mitigation: "These errors are in other programs (CBACT01C, CBACT02C, etc.) and do not affect CBCUS01C task. We will only validate CBCUS01C-specific outputs."

## Inputs

- CBCUS01C.cbl: Source COBOL program to translate
- CBCUS01C_cfg.json (existing): Configuration for CBCUS01C (if exists)
- SYNC-MANIFEST.yaml: Locked numbers reference
- BRANCH-SCOPE.md: Scope discipline rules
- Gate templates from .clinerules/protocol/gates/

## Outputs

- .clinerules/runs/T-2026-05-04-001/G0-decompose.md: This gate file
- .clinerules/runs/T-2026-05-04-001/G1-plan.md: Action plan
- .clinerules/runs/T-2026-05-04-001/G2-scaffold.md: Scaffold status
- .clinerules/runs/T-2026-05-04-001/G3-execute.md: Execution status
- .clinerules/runs/T-2026-05-04-001/G4-validate.md: Validation results
- .clinerules/runs/T-2026-05-04-001/G5-commit.md: Commit status
- .clinerules/runs/T-2026-05-04-001/run.log: Append-only JSON-L event log
- translations/gold-candidate/CBCUS01C.md: Gold-candidate translation
- validation/structure/CBCUS01C_cfg.json: Configuration file

## 7 G0 Questions

### Q1. What is the irreducible unit of work?

**Answer:** CBCUS01C.md gold candidate (one deliverable - the translated Markdown file with 1:1 COBOL logic mapping)

### Q2. What are its inputs?

**Answer:** 
- CBCUS01C.cbl: Source COBOL program to translate
- CBCUS01C_cfg.json (existing): Configuration for CBCUS01C
- SYNC-MANIFEST.yaml: Locked numbers reference (CBSTM03A only, CBCUS01C not yet locked)
- translations/gold-candidate/CBCUS01C.md (if exists): Prior state baseline

### Q3. What are its invariants?

**Answer:**
- paragraphs_expected: 25 (from CBCUS01C_cfg.json after G2 scaffold)
- l01_items_expected: 18 (from CBCUS01C_cfg.json after G2 scaffold)
- reachable_expected: 25 (all paragraphs reachable from entry point)
- dead_paragraphs_allowed: 0 (no dead code)

### Q4. What would prove it correct?

**Answer:** Exact commands + expected outputs:
- `py tools/syncd/sync.py verify` → Exit code 0, CBCUS01C PASS
- `py validation/extract_md_claims.py CBCUS01C` → [OK] status, no lint_warnings_in_claims, no hallucinated_paragraphs
- `py validation/gate_compare.py` → 11/11 PASS (current corpus count)

### Q5. What would prove it wrong?

**Answer:** Failure signatures that trigger halt:
- `py validation/extract_md_claims.py CBCUS01C` returns [ERROR] or [WARN] status
- `py validation/gate_compare.py` returns less than 11/11 PASS
- `py tools/syncd/sync.py verify` exits non-zero
- Any hallucinated_paragraphs detected in CBCUS01C.md
- Any truncation errors detected in CBCUS01C_cfg.json

### Q6. What is explicitly out of scope?

**Answer:** Cross-reference BRANCH-SCOPE.md:
- Branch: main (scope: wave<N>/<program> pattern would apply for new branch)
- Fixing pre-existing errors in other programs (CBACT01C, CBACT02C, CBACT03C, CBACT04C, CBSTM03A, CBSTM03B, CBTRN01C, etc.)
- Modifying validation/ structure files for programs other than CBCUS01C
- Running any batch dispatches or LLM runs
- Editing validators (extract_cfg_summary.py, gate_compare.py, extract_ground_truth.py, extract_md_claims.py, lint_cobol.py)
- Merging PRs (human-only action)

### Q7. What first-principles assumption could be false?

**Answer:** The CBCUS01C.cbl source file is the authoritative source for translation. If the source file was modified after the manifest SHA was recorded, or if there's a mismatch between the .cbl source and the expected structure, this assumption would be false and force re-decomposition at G0.

## Rollback Plan

If G2 or G3 fails:
1. Run `git status -sb` to see current state
2. Run `git diff --stat` to see changes made
3. Run `git checkout .` to discard uncommitted changes
4. If commit was made, run `git reset --hard HEAD~1` to undo commit
5. Update run.log with failure event and next_task_id pointer
