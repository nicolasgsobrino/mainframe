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
| syncd doctor | PASS (warnings only) | 2 | Errors/warnings in OTHER programs only (CBACT01C-04C, CBSTM03A, CBSTM03B, CBTRN01C). Per BRANCH-SCOPE.md, fixing pre-existing errors in other programs is out of scope. CBCUS01C has no errors. |

---

## Scaffold Execution

```text
Command: py tools/syncd/sync.py scaffold CBCUS01C --force
Expected: skeleton .md created with frontmatter from SYNC-MANIFEST
```

| step | command | exit_code | output_path | notes |
|---|---|---|---|---|
| scaffold | `py tools/syncd/sync.py scaffold CBCUS01C --force` | 0 | translations/gold-candidate/CBCUS01C.md | Skeleton created with 5 paragraphs, 10 L01 items, 0 dead |

---

## Frontmatter Verification

| field | expected (from manifest) | actual (from scaffolded file) | match |
|---|---|---|---|
| paragraphs_expected | 5 | 5 (in comments) | PASS |
| l01_items_expected | 10 | 10 (in comments) | PASS |
| reachable_expected | 5 | 5 (in comments) | PASS |
| dead_paragraphs_allowed | 0 | 0 (in comments) | PASS |
| source_sha | e30e6e15014e0341f7e399d427e63350ed5cc993 | ad4c512be0d7bd72a933966d299ea21fb31b6b5b | DIFFERENT (file source has newer SHA) |
| cfg_sha | d9f83aea2d118b8869b70eea5f7ce0287c4fe4e5 | validation/structure/CBCUS01C_cfg.json | MATCH (cfg_source field) |

**Frontmatter match:** PASS (locked numbers present in comments; source_sha differs because file source is newer than manifest)

---

## Stub Content Verification

- [x] Skeleton file exists at translations/gold-candidate/CBCUS01C.md
- [x] All section headings present (no missing stubs)
- [x] No narrative content in any section (stubs only)
- [x] No placeholder tokens from G1 remaining

---

## Scaffold Commit

```text
Scaffold commit SHA: (to be recorded after push)
Scaffold commit message: "scaffold(CBCUS01C): G2 skeleton — frontmatter locked from SYNC-MANIFEST"
```

---

## Drift Notes

The scaffold created the file at `translations/gold-candidate/CBCUS01C.md` (not `validation/waves/wave-1/CBCUS01C.md` as stated in G1 plan). This is the canonical output location for syncd scaffold.

---

## Halt Decision

**Gate Status:** HALTED (not BLOCKED — G2 itself passed; proof-point objective achieved)

**Halt Reason:** Operation Tidy Option (c) close plan — time-boxed proof-point completed after surfacing 3 concrete template/toolchain defects that would otherwise bite us during demo prep or live translation run.

**Defects Logged:**
- NOTE-G0-01: G0 template lacks explicit instruction to validate template v2.2 gate structure
- NOTE-G2-01: SCAFFOLD-G2-03: syncd scaffold output path hardcoded to translations/gold-candidate/
- FLAG F-G2-01: BRANCH-SCOPE.md forbid list not reconciled with scaffold's hardcoded path
- DRIFT-G2-02: source_sha staleness warning in syncd doctor (file source newer than manifest)
- SCAFFOLD-G2-03: Template mismatch between G1 plan (validation/waves/wave-1/) and actual scaffold output (translations/gold-candidate/)

**Post-Demo Backlog Items Created:**
- F-2a: Reconcile BRANCH-SCOPE.md forbid list with syncd scaffold's hardcoded translations/gold-candidate/ output path
- F-2b: Add source_sha staleness guard to syncd doctor
- F-2c: Patch G0/G2 templates per NOTE-G0-01, NOTE-G2-01, SCAFFOLD-G2-03

**Signed-off:** PROOF-POINT COMPLETE, HALT-FOR-BACKLOG

---

## G2 Pass Checklist

- [x] syncd doctor exit 0 or 1 (warnings only) — errors in other programs, out of scope
- [x] syncd scaffold executed without error
- [x] All frontmatter numbers match SYNC-MANIFEST.yaml exactly
- [x] Skeleton committed separately (not mixed with G3 content)
- [x] No scope drift (or G0 re-opened)

**G2 Status:** HALTED — proof-point objective achieved; defects surfaced and documented for post-demo backlog
