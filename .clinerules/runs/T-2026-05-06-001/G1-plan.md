# G1 — PLAN

> **Gate purpose:** Translate G0's irreducible unit into a concrete,
> verbatim-executable action sequence. No discretionary language
> ("as appropriate", "if needed"). A different agent must be able
> to execute this plan without asking any clarifying questions.

---

---
schema_version: "aifirst/2.1"
task_id: "T-2026-05-06-001"
gate: G1
gate_name: "PLAN"
status: PENDING
agent: "qwen3-coder-next-80b"
branch: "preserve/local-progress-2026-05-06"
branch_scope_sha: "4e43543844c5e6167e45c8d33624cc02ce2c6e23"
manifest_sha: "713063e34e48a15fc730121065a974e06f055349"
program_id: "CBACT04C"
locked_numbers_ref: "CBACT04C"
timestamp_open: "2026-05-06T12:11:00Z"
timestamp_close: null
parent_task_id: null
depends_on: ["T-2026-05-06-001/G0"]
override_reason: null
first_principles_revision: null
---

## Locked-Number Snapshot

```yaml
# From SYNC-MANIFEST.yaml @ 713063e34e48a15fc730121065a974e06f055349
program_id: "CBACT04C"
paragraphs_expected: 22
l01_items_expected: 24
reachable_expected: 22
dead_paragraphs_allowed: 0
source_sha: c5e0280e2ed0891877b43eda7bc7c6dc86752421
cfg_sha: 7dfec5b5c5e7c8e968b79cc11c3a04831e8b381f
```

---

## Action Sequence

| step_id | description | command(s) | inputs | outputs | pass criterion | rollback |
|---|---|---|---|---|---|---|
| T-2026-05-06-001-S-001 | syncd doctor pre-check | `py tools/syncd/sync.py doctor` | SYNC-MANIFEST.yaml, existing corpus state | doctor stdout/exit code | exit 0 or 1 (warnings only, no errors) | none (read-only) |
| T-2026-05-06-001-S-002 | syncd scaffold CBACT04C | `py tools/syncd/sync.py scaffold CBACT04C --force` | SYNC-MANIFEST.yaml, validation/structure/CBACT04C_cfg.json | translations/gold-candidate/CBACT04C.md (frontmatter only) | file created, frontmatter numbers match manifest exactly | rm translations/gold-candidate/CBACT04C.md |
| T-2026-05-06-001-S-003 | Commit G2 scaffold skeleton | `git add translations/gold-candidate/CBACT04C.md`, `git commit -m "scaffold(CBACT04C): G2 skeleton — frontmatter locked from SYNC-MANIFEST"`, `git push origin preserve/local-progress-2026-05-06` | translations/gold-candidate/CBACT04C.md (from S-002) | commit SHA recorded, push clean | commit SHA recorded, push clean | git reset --hard HEAD~1 (pre-push) / git revert (post-push) |
| T-2026-05-06-001-S-004 | G3 EXECUTE — fill narrative content | *(human + LLM narrative fill)* | app/cbl/CBACT04C.cbl (c5e0280e), CBACT04C_cfg.json (7dfec5b5) | translations/gold-candidate/CBACT04C.md (narrative filled) | py validation/extract_md_claims.py CBACT04C → [OK], no hallucinated_paragraphs, no lint_warnings_in_claims, frontmatter numbers UNCHANGED from G2 lock | git checkout HEAD -- translations/gold-candidate/CBACT04C.md |
| T-2026-05-06-001-S-005 | G4 VALIDATE + G5 COMMIT | `py tools/syncd/sync.py verify`, `py tools/syncd/sync.py bundle CBACT04C` | translations/gold-candidate/CBACT04C.md (from S-004) | verify exit 0, N/N PASS, lint 0 errors, claims [OK]; bundle commits canonical file set only | if verify FAIL → status=BLOCKED, halt, new task at G0 | N/A (verify is read-only; bundle rollback via git revert) |

---

## File Manifest

| Action | Path | Current SHA | Notes |
|---|---|---|---|
| CREATE | translations/gold-candidate/CBACT04C.md | null | G2 scaffold skeleton |
| CREATE | .clinerules/runs/T-2026-05-06-001/G1-plan.md | null | This gate file |
| CREATE | .clinerules/runs/T-2026-05-06-001/G2-scaffold.md | null | G2 scaffold status |
| CREATE | .clinerules/runs/T-2026-05-06-001/G3-execute.md | null | G3 execution status |
| CREATE | .clinerules/runs/T-2026-05-06-001/G4-validate.md | null | G4 validation status |
| CREATE | .clinerules/runs/T-2026-05-06-001/G5-commit.md | null | G5 commit status |
| MODIFY | .clinerules/runs/T-2026-05-06-001/run.log | null | Append gate_open + gate_close events |

---

## Branch

```text
branch: preserve/local-progress-2026-05-06
```

---

## Risk Flags

| flag | mitigation |
|---|---|
| Source SHA mismatch in CFG JSON (e630901... vs locked c5e0280...) | Verify COBOL source file integrity before G3 narrative fill |
| 22-paragraph complexity (larger than CBACT01C-03C) | Use CFG JSON as anchor to prevent hallucinated paragraphs |

---

## G1 Pass Checklist

- [x] All steps have exact commands (no "run as needed")
- [x] All modified/deleted files have current SHAs recorded
- [x] Locked numbers copied verbatim from SYNC-MANIFEST.yaml
- [x] Plan survives "different agent, verbatim" test
- [x] Risk flags documented

**G1 Status:** PENDING