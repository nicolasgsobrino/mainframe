---
schema_version: "aifirst/2.0"
task_id: "T-2026-05-04-001"
gate: G1
gate_name: "PLAN"
status: PENDING
agent: "qwen3-coder-next-80b"
branch: "main"
branch_scope_sha: "4e43543844c5e6167e45c8d33624cc02ce2c6e23"
manifest_sha: "facee5d1e589d2d112f19e8c73b2cc3497320a79"
program_id: "CBCUS01C"
locked_numbers_ref: "CBCUS01C"
timestamp_open: "2026-05-05T11:22:00Z"
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
- G0: Decompose the problem of promoting CBCUS01C to gold-candidate trust grade (COMPLETED)
- G1: Create a concrete action plan for the promotion
- G2: Scaffolding the CBCUS01C.md file with correct frontmatter
- G3: Execute the narrative content fill for CBCUS01C.md
- G4: Validate using syncd verify command
- G5: Commit the work with full audit trail

## Locked Numbers Snapshot (CBCUS01C)

From SYNC-MANIFEST.yaml after lock:
```
CBCUS01C:
  locked_numbers:
    paragraphs_expected: 5
    l01_items_expected: 10
    reachable_expected: 5
    dead_paragraphs_allowed: 0
    source_sha: e30e6e15014e0341f7e399d427e63350ed5cc993
    cfg_sha: d9f83aea2d118b8869b70eea5f7ce0287c4fe4e5
  locked_at: '2026-05-05T11:22:07Z'
```

## Step Log

| step_id | description | status | timestamp | notes |
|---------|-------------|--------|-----------|-------|
| T-2026-05-04-001-S-001 | py tools/syncd/sync.py scaffold CBCUS01C --force | PENDING | | Create skeleton .md with correct frontmatter |
| T-2026-05-04-001-S-002 | G3 EXECUTE: fill narrative | PENDING | | Fill .md with 1:1 COBOL logic mapping |
| T-2026-05-04-001-S-003 | py tools/syncd/sync.py verify | PENDING | | Mechanical verification via syncd |
| T-2026-05-04-001-S-004 | py tools/syncd/sync.py bundle CBCUS01C | PENDING | | Persist work atomically |

## Step Details

### S-001: SCAFFOLD

**Command:** `py tools/syncd/sync.py scaffold CBCUS01C --force`

**Inputs:**
- SYNC-MANIFEST.yaml (locked_numbers.CBCUS01C)
- CBCUS01C_cfg.json
- CBCUS01C.cbl

**Outputs:**
- translations/gold-candidate/CBCUS01C.md (skeleton with frontmatter)

**PASS criteria:**
- File exists at translations/gold-candidate/CBCUS01C.md
- Frontmatter matches locked_numbers (5 paragraphs, 10 L01 items, 5 reachable, 0 dead)
- No narrative content yet

**Rollback:** `git checkout -- translations/gold-candidate/CBCUS01C.md`

---

### S-002: EXECUTE (G3)

**Command:** *(human + LLM narrative fill)*

**Inputs:**
- skeleton .md (from S-001)
- CBCUS01C.cbl source lines

**Outputs:**
- Complete .md with 1:1 COBOL logic mapping

**PASS criteria:**
- `py validation/extract_md_claims.py CBCUS01C` returns [OK] status
- No lint_warnings_in_claims
- No hallucinated_paragraphs

**Rollback:** `git checkout -- translations/gold-candidate/CBCUS01C.md`

---

### S-003: VALIDATE (G4)

**Command:** `py tools/syncd/sync.py verify`

**PASS criteria:**
- Gate: N/N PASS (current corpus count, no regressions)
- Lint: 62/0/2 baseline preserved
- Claims: [OK] with t04=NULL on new entry
- Exit code 0

**Rollback:** N/A — verify is read-only

---

### S-004: COMMIT (G5)

**Command:** `py tools/syncd/sync.py bundle CBCUS01C`

**PASS criteria:**
- Commit SHA recorded in run.log
- Canonical 4-file set staged and committed
- run.log complete event written

**Rollback:** `git reset --soft HEAD~1`

## Rollback Plan

If S-001 or S-002 fails:
1. Run `git status -sb` to see current state
2. Run `git diff --stat` to see changes made
3. Run `git checkout -- translations/gold-candidate/CBCUS01C.md` to discard changes
4. If commit was made, run `git reset --soft HEAD~1` to undo commit
5. Update run.log with failure event and next_task_id pointer
