# G1 — PLAN

> **Gate purpose:** Translate G0's irreducible unit into a concrete,
> verbatim-executable action sequence. No discretionary language
> ("as appropriate", "if needed"). A different agent must be able
> to execute this plan without asking any clarifying questions.

---

## Locked-Number Snapshot

```yaml
# From SYNC-MANIFEST.yaml @ facee5d1e589d2d112f19e8c73b2cc3497320a79
program_id: "CBCUS01C"
paragraphs_expected: 5
l01_items_expected: 10
reachable_expected: 5
dead_paragraphs_allowed: 0
source_sha: e30e6e15014e0341f7e399d427e63350ed5cc993
cfg_sha: d9f83aea2d118b8869b70eea5f7ce0287c4fe4e5
```

---

## Action Sequence

| step_id | description | command(s) | inputs | outputs | pass criterion | rollback |
|---|---|---|---|---|---|---|
| T-2026-05-05-001-S-001 | syncd doctor pre-check | `py tools/syncd/sync.py doctor` | SYNC-MANIFEST.yaml, existing corpus state | doctor stdout/exit code | exit 0 or 1 (warnings only, no errors) | none (read-only) |
| T-2026-05-05-001-S-002 | syncd scaffold CBCUS01C | `py tools/syncd/sync.py scaffold CBCUS01C --force` | SYNC-MANIFEST.yaml, validation/structure/CBCUS01C_cfg.json | validation/waves/wave-1/CBCUS01C.md (frontmatter only) | file created, frontmatter numbers match manifest exactly | rm validation/waves/wave-1/CBCUS01C.md |
| T-2026-05-05-001-S-003 | Commit G2 scaffold skeleton | `git add validation/waves/wave-1/CBCUS01C.md + gate files`, `git commit -m "scaffold(CBCUS01C): G2 skeleton — frontmatter locked from SYNC-MANIFEST"`, `git push origin main` | validation/waves/wave-1/CBCUS01C.md (from S-002) | commit SHA recorded, push clean | commit SHA recorded, push clean | git reset --hard HEAD~1 (pre-push) / git revert (post-push) |
| T-2026-05-05-001-S-004 | G3 EXECUTE — fill narrative content | *(human + LLM narrative fill)* | app/cbl/CBCUS01C.cbl (e30e6e15), CBCUS01C_cfg.json (d9f83aea) | validation/waves/wave-1/CBCUS01C.md (narrative filled) | py validation/extract_md_claims.py CBCUS01C → [OK], no hallucinated_paragraphs, no lint_warnings_in_claims, frontmatter numbers UNCHANGED from G2 lock | git checkout HEAD -- validation/waves/wave-1/CBCUS01C.md |
| T-2026-05-05-001-S-005 | G4 VALIDATE + G5 COMMIT | `py tools/syncd/sync.py verify`, `py tools/syncd/sync.py bundle CBCUS01C` | validation/waves/wave-1/CBCUS01C.md (from S-004) | verify exit 0, N/N PASS, lint 0 errors, claims [OK]; bundle commits canonical file set only | if verify FAIL → status=BLOCKED, halt, new task at G0 | N/A (verify is read-only; bundle rollback via git revert) |

---

## File Manifest

| Action | Path | Current SHA | Notes |
|---|---|---|---|
| CREATE | validation/waves/wave-1/CBCUS01C.md | null | G2 scaffold skeleton |
| CREATE | .clinerules/runs/T-2026-05-05-001/G1-plan.md | null | This gate file |
| CREATE | .clinerules/runs/T-2026-05-05-001/G2-scaffold.md | null | G2 scaffold status |
| CREATE | .clinerules/runs/T-2026-05-05-001/G3-execute.md | null | G3 execution status |
| CREATE | .clinerules/runs/T-2026-05-05-001/G4-validate.md | null | G4 validation status |
| CREATE | .clinerules/runs/T-2026-05-05-001/G5-commit.md | null | G5 commit status |
| MODIFY | .clinerules/runs/T-2026-05-05-001/run.log | baf2c6045a72f029fe91dda6a826fd9c452c826a | Append gate_open + gate_close events |

---

## Branch

```text
branch: main
```

---

## Risk Flags

| flag | mitigation |
|---|---|
| First use of v2.2 templates end-to-end | halt-and-report at each gate boundary |
| G3 narrative fill is judgment-heavy | cite .cbl line numbers for every claim |

---

## G1 Pass Checklist

- [x] All steps have exact commands (no "run as needed")
- [x] All modified/deleted files have current SHAs recorded
- [x] Locked numbers copied verbatim from SYNC-MANIFEST.yaml
- [x] Plan survives "different agent, verbatim" test
- [x] Risk flags documented

**G1 Status:** PASS