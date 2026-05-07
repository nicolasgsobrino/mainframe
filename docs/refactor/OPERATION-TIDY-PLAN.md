# OPERATION TIDY — Repo Audit + Refactor Plan
> **Step 1 of 3 — DOCUMENT ONLY, NO CHANGES TO EXISTING FILES**
> Generated: 2026-05-05 | Branch: `main` | Operator: MrSnowNB

---

## Section 1 — Current State Snapshot

### Git Metadata
| Field | Value |
|---|---|
| **HEAD SHA** | `45e87200a10e4e1af070b9f35d7aacb3580460fb` |
| **HEAD commit message** | `G2 Scaffold findings` |
| **HEAD commit author** | Mr Snow — 2026-05-05T12:39:46Z |
| **Active branch** | `main` |
| **Remote** | `origin → github.com/MrSnowNB/aws-mainframe-modernization-carddemo` |
| **Active task** | `.clinerules/runs/T-2026-05-04-001` — CBCUS01C at **G2 SCAFFOLD** |

### Tree Depth-2 Listing (top-level directories + immediate children)

```
aws-mainframe-modernization-carddemo/
├── .aifirst/
│   └── runs/
│       ├── T-2026-04-23-001/
│       ├── T-2026-04-23-002/
│       ├── T-2026-04-24-001/
│       ├── T-CBACT01C-T02R-FIX/        ← non-conforming task_id
│       ├── T-CBACT02C-TRANSLATION/     ← non-conforming task_id
│       └── T-PASS1-PASS2-PATCH/        ← non-conforming task_id
├── .clinerules/
│   ├── 00-aifirst-protocol.md          ← v2.1 CANONICAL
│   ├── 01-scope-discipline.md
│   ├── 02-cobol-to-md.md
│   ├── The_Asymptote_of_Bullshit_v2.3.md   ← misplaced
│   ├── scratchpad.md                   ← 0 bytes
│   ├── protocol/
│   │   └── gates/
│   │       ├── G0-plan.template.md     ← STALE v1.0
│   │       ├── G1-scaffold.template.md ← STALE v1.0
│   │       ├── G2-execute.template.md  ← STALE v1.0
│   │       ├── G3-validate.template.md ← STALE v1.0
│   │       └── G4-commit.template.md   ← STALE v1.0
│   └── runs/
│       └── T-2026-05-04-001/           ← ACTIVE TASK (G2 in progress)
├── app/                                ← COBOL source programs (do not touch)
├── demo/                               ← Demo assets
├── diagrams/                           ← Architecture diagrams
├── docs/
│   ├── COBOL-MD-PIPELINE.md
│   ├── COBOL-MD-SCHEMA.md
│   ├── MASTER-ARCHITECTURE.md
│   ├── analysis/
│   ├── audit/
│   └── refactor/                       ← NEW (this document)
│       └── OPERATION-TIDY-PLAN.md
├── samples/                            ← Sample data files
├── scripts/                            ← Utility scripts
├── tools/
│   └── syncd/
│       ├── sync.py                     ← v1.1 CANONICAL CLI
│       ├── README.md
│       └── templates/
│           └── gold_candidate_skeleton.md.j2
├── translations/
│   ├── baseline/                       ← v1.0 translations (6 files)
│   ├── baseline-v1.2/                  ← versioned snapshot (4th copy tier)
│   ├── gold-candidate/                 ← PRIMARY ACTIVE tier (11 files)
│   └── gold/                           ← Graduated tier (1 file only — stub)
├── validation/
│   ├── FOUNDATION_TRACKER.md           ← manually maintained, likely stale
│   ├── README-gate.md
│   ├── cobol_vocab.py
│   ├── extract_cfg_summary.py
│   ├── extract_ground_truth.py
│   ├── extract_md_claims.py
│   ├── gate_compare.py
│   ├── lint_md.py
│   ├── run_rekt_all.py
│   ├── fixtures/
│   ├── lint_cobol/
│   │   ├── lint_cobol.py
│   │   ├── README_LINT.md
│   │   ├── lint_results/
│   │   └── rules/
│   ├── pass1/                          ← legacy pass naming (~20 JSON files)
│   ├── pass2/
│   ├── pass3/
│   ├── rekt/                           ← informal triage dump zone
│   ├── structure/                      ← CFG JSON outputs (13 files)
│   │   └── COCRDUPC.cbl.report/        ← anomalous directory with .report ext
│   └── tools/                          ← ambiguous vs root tools/
├── AiFirst Protocol — Master Specification & Gate Templates.md  ← STALE DUPE
├── BRANCH-SCOPE.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── DEMO-SPRINT-PLAN.md                 ← misplaced operational artifact
├── ISSUE.md                            ← misplaced scratch note
├── LICENSE
├── NOTICE
├── PATCH-PLAN.md                       ← misplaced operational artifact
├── README.md
├── REPLICATION-NOTES.md                ← misplaced operational artifact
├── SYNC-MANIFEST.yaml
├── TROUBLESHOOTING.md                  ← misplaced operational artifact
└── cocrdlic_log.txt                    ← 320 KB raw log in root
```

### File Counts Per Top-Level Directory

| Directory | Files (approx) | Notes |
|---|---|---|
| `.aifirst/runs/` | 6 task dirs (unknown file count inside) | Legacy v1.0 run store |
| `.clinerules/` | 8 files + 5 gate templates + 1 active run dir | Mixed active + stale |
| `app/` | ~40+ COBOL programs | Canonical source, untouched |
| `demo/` | Unknown | Not audited |
| `diagrams/` | Unknown | Not audited |
| `docs/` | 3 root `.md` + 2 subdirs | Clean |
| `samples/` | Unknown | Not audited |
| `scripts/` | Unknown | Unclear overlap with `tools/` |
| `tools/syncd/` | 3 files + 1 template | Active, current |
| `translations/baseline/` | 6 `.md` files | v1.0 tier |
| `translations/baseline-v1.2/` | Unknown | 4th copy tier |
| `translations/gold-candidate/` | 11 `.md` files | Primary active |
| `translations/gold/` | 1 `.md` file | Near-empty tier |
| `validation/pass1/` | ~18 JSON + 4 subdirs | Legacy pass naming |
| `validation/pass2/` | Unknown | Legacy pass naming |
| `validation/pass3/` | Unknown | Legacy pass naming |
| `validation/rekt/` | Unknown | Informal dump zone |
| `validation/structure/` | 13 JSON + 1 anomalous dir | Active |
| Root level `.md` files | 12 | 4-5 misplaced |
| Root level other | 3 (LICENSE, NOTICE, SYNC-MANIFEST.yaml, .gitignore) | Keep |

### Notable File Sizes

| File | Size | Flag |
|---|---|---|
| `cocrdlic_log.txt` | 320 KB | 🔴 Raw log committed to root |
| `validation/structure/COCRDUPC_cfg.json` | 452 KB | 🔴 60× larger than peers |
| `validation/pass1/COCRDUPC_annotations.json` | 234 KB | ⚠️ Explosion artifact |
| `translations/baseline/CBACT01C.md` | 41 KB | ⚠️ 2× size of gold-candidate version |
| `translations/baseline/CBTRN01C.md` | 38 KB | ⚠️ 1.5× size of gold-candidate version |
| `.clinerules/00-aifirst-protocol.md` | 14 KB | ✅ Normal |
| `AiFirst Protocol — Master Specification & Gate Templates.md` | 19 KB | 🔴 Stale root duplicate |

---

## Section 2 — Identified Issues

### 🔴 Critical Issues

| ID | Files/Paths Affected | Risk if Left Unchanged | Proposed Resolution | Target Step |
|---|---|---|---|---|
| **C1** | `AiFirst Protocol — Master Specification & Gate Templates.md` (root) | **HIGH** — Any agent that loads this v1.0 file instead of `.clinerules/00-aifirst-protocol.md` will operate under the wrong gate schema, missing G0 DECOMPOSE and using deprecated gate names. Silent wrong-protocol execution. | **Delete** from root (archive first to `archive/protocol-v1.0/`) | Step 2 |
| **C2** | `.clinerules/protocol/gates/G0-plan.template.md` through `G4-commit.template.md` (5 files) | **HIGH** — All 5 templates use v1.0 naming (G0=PLAN, G1=SCAFFOLD, G2=EXECUTE, G3=VALIDATE, G4=COMMIT). Protocol is now v2.1 with 6 gates (G0=DECOMPOSE, G1=PLAN, G2=SCAFFOLD, G3=EXECUTE, G4=VALIDATE, G5=COMMIT). Any agent using these templates will produce malformed run artifacts. | **Archive** to `archive/protocol-v1.0/gates/` and **author new v2.1 templates** in Step 3 | Step 2 + 3 |
| **C3** | `cocrdlic_log.txt` (root, 320 KB) | **MEDIUM-HIGH** — 320 KB binary-ish log in root inflates clone size, pollutes `git status`, and implies `.gitignore` is not covering log output. Will grow if more runs execute without gitignore fix. | **Delete** from repo; **add `*.log` and `*.txt` log patterns to `.gitignore`** | Step 2 |
| **C4** | `validation/structure/COCRDUPC_cfg.json` (452 KB) and `validation/pass1/COCRDUPC_annotations.json` (234 KB) | **MEDIUM** — COCRDUPC appears to have triggered a CFG explosion in `extract_cfg_summary.py` (likely unbounded recursion or loop unrolling). These files are 60× and 30× the size of peer files, suggesting corrupted/runaway output rather than legitimate analysis. They will cause timeout/OOM failures in any downstream batch runs. | **Investigate** the extractor bug; **archive** the bloated outputs; **re-run** COCRDUPC after bug fix in Step 3 | Step 2 + 3 |
| **C5** | `.aifirst/runs/` (entire directory) vs `.clinerules/runs/` | **MEDIUM** — Two competing run-store locations exist. Agents may not know which is canonical. `.aifirst/runs/` uses v1.0 schema and some entries have non-conforming task IDs (no date stamp). New runs should always go to `.clinerules/runs/`. | **Archive** `.aifirst/` entirely to `archive/legacy-runs-v1.0/`; update any scripts that reference `.aifirst/` | Step 2 |

### ⚠️ Medium Issues

| ID | Files/Paths Affected | Risk if Left Unchanged | Proposed Resolution | Target Step |
|---|---|---|---|---|
| **M1** | `translations/baseline/COBSWAIT.md`, `translations/gold-candidate/COBSWAIT.md`, `translations/gold/COBSWAIT.md` | **MEDIUM** — COBSWAIT.md has been independently edited in 3 tiers with slightly different sizes, creating diverged content. No sync mechanism exists between tiers. Future gate_compare runs may produce incorrect diffs. | **Consolidate**: Keep gold-candidate as canonical; move gold/ version (only 1 file, promoted) to `archive/translations-tier-review/`; keep baseline as read-only reference | Step 3 |
| **M2** | `translations/gold/` (1 file only: COBSWAIT.md) | **LOW-MEDIUM** — The `gold/` tier was either abandoned after one promotion or COBSWAIT was incorrectly promoted in isolation. An empty tier confuses the pipeline's tier model. | **Decision required**: Either populate `gold/` intentionally (graduate programs from gold-candidate as they pass all gates) OR rename to `archive/translations-tier-review/`. Do not delete history. | Step 3 |
| **M3** | `translations/baseline-v1.2/` | **LOW** — A 4th translation copy tier with no clear pipeline role. Versioning should be handled by git tags, not directory copies. | **Archive** to `archive/translations-baseline-v1.2/` | Step 2 |
| **M4** | `validation/FOUNDATION_TRACKER.md` | **LOW-MEDIUM** — Manually maintained tracker almost certainly drifts from actual validation state over time. If agents read this for decision-making, stale data causes wrong skip/proceed calls. | **Move** to `docs/audit/FOUNDATION_TRACKER.md`; add note at top that canonical state is generated by `syncd doctor`; plan automated regeneration in Step 3 | Step 3 |
| **M5** | `validation/pass1/`, `validation/pass2/`, `validation/pass3/`, `validation/rekt/` | **MEDIUM** — These are informally named legacy output directories. `pass1/pass2/pass3` reflects a superseded wave-based naming scheme. `rekt/` is an informal dump zone. New convention should be gate-based per `validation/structure/`. | **Rename** pass1/2/3 to `validation/waves/wave-1/`, `wave-2/`, `wave-3/` OR archive them. Keep `rekt/` renamed to `validation/triage/` with a README. | Step 3 |
| **M6** | `validation/tools/` vs `tools/syncd/` | **MEDIUM** — Two tool locations create confusion about where to find/add tooling. `validation/tools/` is nested inside validation scope while `tools/syncd/` is the canonical CLI. | **Inventory** `validation/tools/` contents; merge anything non-redundant into `tools/` or `tools/validation-helpers/`; remove `validation/tools/` stub if empty | Step 3 |
| **M7** | `DEMO-SPRINT-PLAN.md`, `PATCH-PLAN.md`, `REPLICATION-NOTES.md`, `TROUBLESHOOTING.md` (all root level) | **LOW** — Operational planning docs cluttering root, which should only contain project identity files (README, LICENSE, NOTICE, CODE_OF_CONDUCT, CONTRIBUTING) and config files (SYNC-MANIFEST.yaml, BRANCH-SCOPE.md, .gitignore). | **Move** all four to `docs/ops/` | Step 3 |
| **M8** | `.clinerules/The_Asymptote_of_Bullshit_v2.3.md` | **LOW** — Valuable philosophical document about AI reliability / hallucination, but: (a) wrong location inside `.clinerules/` which is for agent rules files, (b) naming convention breaks the `00-NN-name.md` schema of siblings. | **Move** to `docs/philosophy/THE-ASYMPTOTE.md` | Step 3 |
| **M9** | `.aifirst/runs/T-CBACT01C-T02R-FIX/`, `T-CBACT02C-TRANSLATION/`, `T-PASS1-PASS2-PATCH/` | **LOW** — Three task directories with non-conforming task IDs (no `T-YYYY-MM-DD-NNN` schema). Breaks any tooling that parses run directories by date pattern. | **Subsumed by M5/C5** — archive the entire `.aifirst/` tree | Step 2 |
| **M10** | `ISSUE.md` (root level) | **LOW** — Ad-hoc issue scratch note masquerading as a root document. Has no defined schema or lifecycle. | **Delete** (contents likely captured elsewhere); if it has unique content, move to `docs/ops/ISSUE-LOG.md` first | Step 2 |

### 🟡 Low Issues

| ID | Files/Paths Affected | Risk if Left Unchanged | Proposed Resolution | Target Step |
|---|---|---|---|---|
| **L1** | `.clinerules/scratchpad.md` (0 bytes) | **VERY LOW** — Zero-byte file committed to repo. No content. Wastes an object. | **Delete** | Step 2 |
| **L2** | `scripts/` (unknown contents) vs `tools/` | **LOW** — Two automation directories. If `scripts/` contains utilities that duplicate or complement `tools/syncd/`, the split creates maintenance confusion. | **Inventory** `scripts/` in Step 3; consolidate or clearly separate by purpose | Step 3 |
| **L3** | `validation/structure/COCRDUPC.cbl.report/` (directory with `.report` extension) | **LOW** — Unusual naming convention — a directory with a `.report` extension. Likely a debug artifact from the COCRDUPC extractor run. Confusing to tooling and humans. | **Move** to `validation/structure/reports/COCRDUPC/` in Step 3 | Step 3 |
| **L4** | `translations/baseline/` has 6 files; `gold-candidate/` has 11 — no clear promotion policy documented | **LOW** — No `TRANSLATION-TIER-POLICY.md` exists. It is unclear under what conditions a baseline translation graduates to gold-candidate, or gold-candidate to gold. | **Author** `docs/refactor/TRANSLATION-TIER-POLICY.md` in Step 3 | Step 3 |

### ✅ Confirmed Clean

| Area | Status | Notes |
|---|---|---|
| `app/` | ✅ Clean | Canonical COBOL source. No changes ever. |
| `.clinerules/00-aifirst-protocol.md` | ✅ Clean | v2.1 canonical protocol |
| `.clinerules/01-scope-discipline.md` | ✅ Clean | Active scope enforcement |
| `.clinerules/02-cobol-to-md.md` | ✅ Clean | Active translation rules |
| `.clinerules/runs/T-2026-05-04-001/` | ✅ Active | **PROTECTED** — do not touch |
| `tools/syncd/sync.py` | ✅ Clean | v1.1 canonical CLI |
| `tools/syncd/README.md` | ✅ Clean | |
| `tools/syncd/templates/` | ✅ Clean | v1.1 templates |
| `BRANCH-SCOPE.md` | ✅ Clean | SHA-pinned by protocol gates |
| `SYNC-MANIFEST.yaml` | ✅ Clean | Locked program numbers |
| `README.md` | ✅ Clean | Public-facing project overview |
| `LICENSE`, `NOTICE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md` | ✅ Clean | Standard GitHub files |
| `.gitignore` | ✅ Clean (needs update) | Will need `*.log` / `cocrdlic_log.txt` entry |
| `validation/structure/*.json` (except COCRDUPC) | ✅ Clean | CFG outputs, 1-7 KB each |
| `validation/lint_cobol/` | ✅ Clean | Active linter + rules |
| `validation/pass1/` (except COCRDUPC files) | ✅ Clean | Well-structured annotation JSONs |
| `translations/gold-candidate/` (11 files) | ✅ Clean | Primary active translation tier |
| `docs/COBOL-MD-PIPELINE.md` | ✅ Clean | |
| `docs/COBOL-MD-SCHEMA.md` | ✅ Clean | |
| `docs/MASTER-ARCHITECTURE.md` | ✅ Clean | |
| `docs/analysis/`, `docs/audit/` | ✅ Clean | |

---

## Section 3 — Proposed Target Tree

```
aws-mainframe-modernization-carddemo/
│
├── .aifirst/                              (archive: → archive/legacy-runs-v1.0/.aifirst/)
│
├── .clinerules/
│   ├── 00-aifirst-protocol.md             (keep)
│   ├── 01-scope-discipline.md             (keep)
│   ├── 02-cobol-to-md.md                  (keep)
│   ├── The_Asymptote_of_Bullshit_v2.3.md  (move: → docs/philosophy/THE-ASYMPTOTE.md)
│   ├── scratchpad.md                      (delete)
│   ├── protocol/
│   │   └── gates/
│   │       ├── G0-plan.template.md        (archive: → archive/protocol-v1.0/gates/)
│   │       ├── G1-scaffold.template.md    (archive: → archive/protocol-v1.0/gates/)
│   │       ├── G2-execute.template.md     (archive: → archive/protocol-v1.0/gates/)
│   │       ├── G3-validate.template.md    (archive: → archive/protocol-v1.0/gates/)
│   │       ├── G4-commit.template.md      (archive: → archive/protocol-v1.0/gates/)
│   │       ├── G0-decompose.template.md   (new — v2.1)
│   │       ├── G1-plan.template.md        (new — v2.1)
│   │       ├── G2-scaffold.template.md    (new — v2.1)
│   │       ├── G3-execute.template.md     (new — v2.1)
│   │       ├── G4-validate.template.md    (new — v2.1)
│   │       └── G5-commit.template.md      (new — v2.1)
│   └── runs/
│       └── T-2026-05-04-001/              (keep — ACTIVE TASK, DO NOT TOUCH)
│
├── app/                                   (keep — untouched)
│
├── archive/                               (new — Step 2 archive root)
│   ├── legacy-runs-v1.0/
│   │   └── .aifirst/                      (archive: from .aifirst/)
│   ├── protocol-v1.0/
│   │   └── gates/                         (archive: from .clinerules/protocol/gates/ v1.0 files)
│   ├── translations-baseline-v1.2/        (archive: from translations/baseline-v1.2/)
│   └── translations-tier-review/
│       └── gold/                          (archive: from translations/gold/)
│
├── demo/                                  (keep)
├── diagrams/                              (keep)
│
├── docs/
│   ├── COBOL-MD-PIPELINE.md               (keep)
│   ├── COBOL-MD-SCHEMA.md                 (keep)
│   ├── MASTER-ARCHITECTURE.md             (keep)
│   ├── analysis/                          (keep)
│   ├── audit/                             (keep)
│   ├── ops/                               (new)
│   │   ├── DEMO-SPRINT-PLAN.md            (move: from root)
│   │   ├── PATCH-PLAN.md                  (move: from root)
│   │   ├── REPLICATION-NOTES.md           (move: from root)
│   │   └── TROUBLESHOOTING.md             (move: from root)
│   ├── philosophy/                        (new)
│   │   └── THE-ASYMPTOTE.md               (move: from .clinerules/The_Asymptote_of_Bullshit_v2.3.md)
│   └── refactor/
│       ├── OPERATION-TIDY-PLAN.md         (keep — this document)
│       └── TRANSLATION-TIER-POLICY.md     (new — Step 3)
│
├── samples/                               (keep)
├── scripts/                               (keep — audit in Step 3, consolidate if needed)
│
├── tools/
│   └── syncd/
│       ├── sync.py                        (keep)
│       ├── README.md                      (keep)
│       └── templates/
│           └── gold_candidate_skeleton.md.j2  (keep)
│
├── translations/
│   ├── baseline/                          (keep — read-only reference; add README)
│   ├── baseline-v1.2/                     (archive: → archive/translations-baseline-v1.2/)
│   ├── gold-candidate/                    (keep — primary active tier)
│   └── gold/                             (archive: → archive/translations-tier-review/gold/)
│
├── validation/
│   ├── FOUNDATION_TRACKER.md              (move: → docs/audit/FOUNDATION_TRACKER.md)
│   ├── README-gate.md                     (keep)
│   ├── cobol_vocab.py                     (keep)
│   ├── extract_cfg_summary.py             (keep — fix COCRDUPC bug in Step 3)
│   ├── extract_ground_truth.py            (keep)
│   ├── extract_md_claims.py               (keep)
│   ├── gate_compare.py                    (keep)
│   ├── lint_md.py                         (keep)
│   ├── run_rekt_all.py                    (keep)
│   ├── fixtures/                          (keep)
│   ├── lint_cobol/                        (keep)
│   ├── pass1/                             (keep — rename to waves/wave-1/ in Step 3)
│   ├── pass2/                             (keep — rename to waves/wave-2/ in Step 3)
│   ├── pass3/                             (keep — rename to waves/wave-3/ in Step 3)
│   ├── rekt/                              (keep — rename to triage/ + add README in Step 3)
│   ├── structure/
│   │   ├── *.json (non-COCRDUPC)          (keep)
│   │   ├── COCRDUPC_cfg.json              (archive: after bug investigation)
│   │   └── COCRDUPC.cbl.report/           (move: → validation/structure/reports/COCRDUPC/)
│   └── tools/                             (keep — audit and consolidate in Step 3)
│
├── AiFirst Protocol — Master Specification & Gate Templates.md  (archive: → archive/protocol-v1.0/)
├── BRANCH-SCOPE.md                        (keep)
├── CODE_OF_CONDUCT.md                     (keep)
├── CONTRIBUTING.md                        (keep)
├── DEMO-SPRINT-PLAN.md                    (move: → docs/ops/)
├── ISSUE.md                               (delete)
├── LICENSE                                (keep)
├── NOTICE                                 (keep)
├── PATCH-PLAN.md                          (move: → docs/ops/)
├── README.md                              (keep)
├── REPLICATION-NOTES.md                   (move: → docs/ops/)
├── SYNC-MANIFEST.yaml                     (keep)
├── TROUBLESHOOTING.md                     (move: → docs/ops/)
├── cocrdlic_log.txt                       (delete)
└── .gitignore                             (keep — update to add *.log pattern)
```

---

## Section 4 — Step 2 CLEANUP Execution Plan

> **Scope:** Delete stale files, archive legacy artifacts. No renames of active files.
> **Pre-condition:** Section 8 approval gate must be fully checked before Step 2 begins.
> **Active task guard:** T-2026-05-04-001 is NOT touched. `.clinerules/runs/` is NOT touched.

### Operations (ordered by risk — lowest impact first)

---

**OP-2-01: Delete zero-byte scratchpad**
```bash
git rm .clinerules/scratchpad.md
```
- Files: `.clinerules/scratchpad.md`
- Reversibility: `git revert HEAD -- .clinerules/scratchpad.md` or `git reset HEAD~1`
- Verification: `git status` shows file removed; `ls .clinerules/` no longer shows it
- Pre-condition: Confirm file is 0 bytes (`wc -c .clinerules/scratchpad.md` → 0)

---

**OP-2-02: Delete ISSUE.md from root**
```bash
git rm ISSUE.md
```
- Files: `ISSUE.md`
- Reversibility: `git reset HEAD~1`
- Verification: `ls *.md` at root does not include ISSUE.md
- Pre-condition: Confirm contents are not unique (read file first); if any unique content, copy to `docs/ops/ISSUE-LOG.md` first
- **Status: ✅ EXECUTED at commit a198dc7 in Commit A (Step 2, 2026-05-04)**

---

**OP-2-03: Delete cocrdlic_log.txt from root + update .gitignore**
```bash
git rm cocrdlic_log.txt
echo "*.log" >> .gitignore
echo "cocrdlic_log.txt" >> .gitignore
git add .gitignore
```
- Files: `cocrdlic_log.txt`, `.gitignore`
- Reversibility: `git reset HEAD~1` restores both; remove the added `.gitignore` lines
- Verification: `ls *.txt` at root empty; `git status` clean; `cat .gitignore | grep log` shows entry
- Pre-condition: Confirm file is a raw log (not a reference document); `head -20 cocrdlic_log.txt`

---

**OP-2-04: Create archive/ directory structure**
```bash
mkdir -p archive/legacy-runs-v1.0
mkdir -p archive/protocol-v1.0/gates
mkdir -p archive/translations-baseline-v1.2
mkdir -p archive/translations-tier-review/gold
```
- Files: New directories only
- Reversibility: `rm -rf archive/`
- Verification: `ls archive/` shows 4 subdirs
- Pre-condition: None — creation only

---

**OP-2-05: Archive stale root protocol document**
```bash
git mv "AiFirst Protocol — Master Specification & Gate Templates.md" \
  "archive/protocol-v1.0/AiFirst-Protocol-v1.0-ARCHIVED.md"
```
- Files: Root `AiFirst Protocol — Master Specification & Gate Templates.md`
- Reversibility: `git mv archive/protocol-v1.0/AiFirst-Protocol-v1.0-ARCHIVED.md "AiFirst Protocol — Master Specification & Gate Templates.md"`
- Verification: `ls archive/protocol-v1.0/` shows the file; `ls *.md` at root does not
- Pre-condition: Confirm `.clinerules/00-aifirst-protocol.md` is the canonical v2.1 doc

---

**OP-2-06: Archive v1.0 gate templates**
```bash
git mv .clinerules/protocol/gates/G0-plan.template.md      archive/protocol-v1.0/gates/
git mv .clinerules/protocol/gates/G1-scaffold.template.md  archive/protocol-v1.0/gates/
git mv .clinerules/protocol/gates/G2-execute.template.md   archive/protocol-v1.0/gates/
git mv .clinerules/protocol/gates/G3-validate.template.md  archive/protocol-v1.0/gates/
git mv .clinerules/protocol/gates/G4-commit.template.md    archive/protocol-v1.0/gates/
```
- Files: All 5 `.clinerules/protocol/gates/G*.template.md`
- Reversibility: `git mv` each file back; or `git reset HEAD~1`
- Verification: `ls .clinerules/protocol/gates/` shows no v1.0 files; `ls archive/protocol-v1.0/gates/` shows all 5
- Pre-condition: Confirm new v2.1 templates will be created in OP-3 before any agent runs use gates

---

**OP-2-07: Archive entire .aifirst/ legacy run store**
```bash
git mv .aifirst archive/legacy-runs-v1.0/.aifirst
```
- Files: Entire `.aifirst/` directory tree
- Reversibility: `git mv archive/legacy-runs-v1.0/.aifirst .aifirst`
- Verification: `ls -la` at root does not show `.aifirst/`; `ls archive/legacy-runs-v1.0/` shows `.aifirst/`
- Pre-condition: Confirm no active scripts reference `.aifirst/` path; `grep -r ".aifirst" tools/ scripts/ .clinerules/` returns nothing critical

---

**OP-2-08: Archive translations/baseline-v1.2/**
```bash
git mv translations/baseline-v1.2 archive/translations-baseline-v1.2/
```
- Files: Entire `translations/baseline-v1.2/` directory
- Reversibility: `git mv archive/translations-baseline-v1.2 translations/baseline-v1.2`
- Verification: `ls translations/` does not show `baseline-v1.2/`
- Pre-condition: Confirm no active script or syncd command references `translations/baseline-v1.2`

---

**OP-2-09: Archive translations/gold/ (stub tier)**
```bash
git mv translations/gold archive/translations-tier-review/gold
```
- Files: `translations/gold/` (contains only `COBSWAIT.md`)
- Reversibility: `git mv archive/translations-tier-review/gold translations/gold`
- Verification: `ls translations/` shows: `baseline/`, `baseline-v1.2/` (gone), `gold-candidate/`, no `gold/`
- Pre-condition: Decision confirmed that gold/ tier is not actively used; consult SYNC-MANIFEST.yaml to verify no reference to `translations/gold/`

---

**Step 2 Commit:**
```bash
git add -A
git commit -m "chore(tidy): Operation Tidy Step 2 — delete stale files, archive legacy artifacts

- Delete: cocrdlic_log.txt (320KB log), ISSUE.md, scratchpad.md
- Archive: AiFirst Protocol v1.0 root doc → archive/protocol-v1.0/
- Archive: 5× v1.0 gate templates → archive/protocol-v1.0/gates/
- Archive: .aifirst/ legacy run store → archive/legacy-runs-v1.0/
- Archive: translations/baseline-v1.2/ → archive/translations-baseline-v1.2/
- Archive: translations/gold/ (stub) → archive/translations-tier-review/gold/
- Update: .gitignore adds *.log pattern
- Create: archive/ directory structure

No active files modified. Active task T-2026-05-04-001 untouched.
Approval gate Section 8 confirmed before execution."
```

---

## Section 5 — Step 3 REFACTOR Execution Plan

> **Scope:** Relocations, new documents, protocol version bump. No deletions.
> **Pre-condition:** Step 2 commit is clean and verified. T-2026-05-04-001 CBCUS01C task complete or paused.

### New Directories to Create

```bash
mkdir -p docs/ops
mkdir -p docs/philosophy
mkdir -p validation/waves/wave-1
mkdir -p validation/waves/wave-2
mkdir -p validation/waves/wave-3
mkdir -p validation/triage
mkdir -p validation/structure/reports/COCRDUPC
```

### File Relocations

| Operation | From | To | Rationale |
|---|---|---|---|
| git mv | `DEMO-SPRINT-PLAN.md` | `docs/ops/DEMO-SPRINT-PLAN.md` | Operational doc off root |
| git mv | `PATCH-PLAN.md` | `docs/ops/PATCH-PLAN.md` | Operational doc off root |
| git mv | `REPLICATION-NOTES.md` | `docs/ops/REPLICATION-NOTES.md` | Operational doc off root |
| git mv | `TROUBLESHOOTING.md` | `docs/ops/TROUBLESHOOTING.md` | Operational doc off root |
| git mv | `.clinerules/The_Asymptote_of_Bullshit_v2.3.md` | `docs/philosophy/THE-ASYMPTOTE.md` | Misplaced in agent-rules dir |
| git mv | `validation/FOUNDATION_TRACKER.md` | `docs/audit/FOUNDATION_TRACKER.md` | Doc belongs in docs/, not validation root |
| git mv | `validation/pass1/` contents | `validation/waves/wave-1/` | Legacy naming → canonical naming |
| git mv | `validation/pass2/` contents | `validation/waves/wave-2/` | Legacy naming → canonical naming |
| git mv | `validation/pass3/` contents | `validation/waves/wave-3/` | Legacy naming → canonical naming |
| git mv | `validation/rekt/` contents | `validation/triage/` | Informal → formal naming |
| git mv | `validation/structure/COCRDUPC.cbl.report/` | `validation/structure/reports/COCRDUPC/` | Normalize dir name |

### New Documents to Author

| Path | Purpose | Schema / Required Sections |
|---|---|---|
| `docs/refactor/TRANSLATION-TIER-POLICY.md` | Define promotion rules between translation tiers | Tier definitions (baseline → gold-candidate → gold); Gate criteria for promotion; Demotion policy; COBSWAIT special-case note |
| `docs/ops/README.md` | Index for the ops/ directory | Links to each doc; brief description; maintenance owner |
| `docs/philosophy/README.md` | Context for philosophy docs | What these docs are; how they inform agent behavior |
| `validation/triage/README.md` | Explains triage/ dir purpose | What "triage" means; how programs enter/exit; who reviews |
| `validation/waves/README.md` | Explains wave-1/2/3 structure | What each wave covered; date range; programs included |
| `archive/README.md` | Index of archived material | Each subdir, what it contains, why archived, SHA of original commit |

### Protocol Version Bump (v2.1 → v2.2)

Update `.clinerules/00-aifirst-protocol.md` with the following additions:

1. **Add Section: Gate Templates Location** — explicitly state canonical templates are at `.clinerules/protocol/gates/G{0-5}-*.template.md` (not `protocol/gates/G{0-4}` which is now archived)
2. **Add Section: Run Store Location** — explicitly state canonical run store is `.clinerules/runs/T-YYYY-MM-DD-NNN/` (NOT `.aifirst/runs/`)
3. **Add Section: Archive Policy** — describe `archive/` directory structure and when to use it
4. **Bump version header** from v2.1 to v2.2

### New v2.1 Gate Templates (6 files)

```
.clinerules/protocol/gates/G0-decompose.template.md
.clinerules/protocol/gates/G1-plan.template.md
.clinerules/protocol/gates/G2-scaffold.template.md
.clinerules/protocol/gates/G3-execute.template.md
.clinerules/protocol/gates/G4-validate.template.md
.clinerules/protocol/gates/G5-commit.template.md
```

Each template must include:
- Gate ID + Name + Description
- Required input fields (what the agent must have before entering this gate)
- Required output fields (what the agent must produce to pass this gate)
- Fail criteria (explicit conditions that block gate passage)
- Human approval requirement (Y/N/conditional)

### COCRDUPC Bug Investigation (Step 3 action item)

Before archiving and re-running COCRDUPC:
1. Read `validation/extract_cfg_summary.py` — identify the loop/recursion handling for PERFORM THRU
2. COCRDUPC is the largest CardDemo program (complex CICS transaction) — it likely has deeply nested PERFORM THRU chains
3. Add a `max_depth` guard and `visited_paragraphs` set to prevent infinite traversal
4. Archive bloated outputs: `COCRDUPC_cfg.json`, `COCRDUPC_annotations.json`
5. Re-run extractor on COCRDUPC only
6. Verify new output is ≤ 20 KB (comparable to CBACT04C at 7 KB, accounting for program size)

**Step 3 Commit:**
```bash
git add -A
git commit -m "refactor(tidy): Operation Tidy Step 3 — relocations, new docs, protocol v2.2

- Move: 4 operational docs to docs/ops/
- Move: THE-ASYMPTOTE to docs/philosophy/
- Move: FOUNDATION_TRACKER to docs/audit/
- Move: validation/pass1-3 to validation/waves/wave-1-3/
- Move: validation/rekt to validation/triage/
- Move: COCRDUPC.cbl.report/ to validation/structure/reports/COCRDUPC/
- New: docs/refactor/TRANSLATION-TIER-POLICY.md
- New: 6 gate templates v2.1 (G0-decompose through G5-commit)
- New: README files for new directories
- Update: .clinerules/00-aifirst-protocol.md → v2.2
- Fix: extract_cfg_summary.py COCRDUPC depth explosion bug

Active task T-2026-05-04-001 unaffected."
```

---

## Section 6 — Rollback Procedure

### If Step 2 needs rollback

```bash
# Full revert of Step 2 commit
git revert HEAD   # creates a new revert commit
# OR to hard-reset (loses commit history):
git reset --hard 45e87200a10e4e1af070b9f35d7aacb3580460fb
git push --force-with-lease origin main
```

- **Pre-Step-2 SHA:** `45e87200a10e4e1af070b9f35d7aacb3580460fb`
- **Impact on T-2026-05-04-001:** NONE — task files are in `.clinerules/runs/T-2026-05-04-001/` which Step 2 does not touch
- **Verification after rollback:** `ls .aifirst/` exists; `ls "AiFirst Protocol*.md"` exists; `cocrdlic_log.txt` exists; `ls .clinerules/scratchpad.md` exists

### If Step 3 needs rollback

```bash
# Revert Step 3 commit
git revert HEAD
# OR hard reset to Step 2 commit (record its SHA after Step 2 completes)
git reset --hard <STEP-2-SHA>
git push --force-with-lease origin main
```

- **Impact on T-2026-05-04-001:** NONE — Step 3 does not touch `.clinerules/runs/`
- **Impact on protocol:** Rolling back Step 3 restores v2.1 protocol; gate templates revert to v1.0 archives (Step 2 archived them) — this means gate templates would be temporarily absent until Step 3 is re-run. Mitigate by re-authoring templates before rolling back if agents are active.

### Rollback Decision Matrix

| Scenario | Action | Notes |
|---|---|---|
| Step 2 archived wrong file | `git revert HEAD` | Single-commit revert is safe |
| Step 3 broke active tooling | `git revert HEAD` | Only Step 3 commit is reverted |
| Both steps need rollback | Hard reset to `45e87200` | Use `--force-with-lease` |
| T-2026-05-04-001 is corrupted | Restore files from SHA `45e87200` | `git checkout 45e87200 -- .clinerules/runs/T-2026-05-04-001/` |

---

## Section 7 — Active Task Protection

### ⚠️ MANDATORY PROTECTION DECLARATION

The following task and ALL its contents are **EXPLICITLY PROTECTED** and **MUST NOT BE TOUCHED** in any step of Operation Tidy:

```
.clinerules/runs/T-2026-05-04-001/
├── G0-decompose.md        ← DO NOT TOUCH
├── G1-plan.md             ← DO NOT TOUCH
├── G2-scaffold.md         ← DO NOT TOUCH (in progress as of HEAD)
├── FINDINGS.md            ← DO NOT TOUCH (if present)
└── run.log                ← DO NOT TOUCH
```

**Program:** CBCUS01C — Customer Master translation revision
**Current gate:** G2 SCAFFOLD (confirmed by HEAD commit message "G2 Scaffold findings")
**Task status:** ACTIVE — do not pause, interrupt, or restructure until task reaches G5-COMMIT

**Why this matters:**
- T-2026-05-04-001 is a live work artifact; any modification corrupts the audit trail
- The `.clinerules/runs/` directory is the canonical run store post-v2.0 protocol
- Operation Tidy is a parallel housekeeping effort and must not race with active translation work
- If CBCUS01C completes (reaches G5) during Step 2/3 execution, its run directory simply becomes a historical record — still do not touch it

**Enforcement rule:** Before executing ANY `git mv`, `git rm`, or file-write operation in Steps 2 or 3, verify the target path does NOT start with `.clinerules/runs/T-2026-05-04-001`.

---

## Section 8 — Approval Gate

> **Instructions:** Mark each checkbox `[x]` only after manual review. Step 2 MUST NOT begin until all boxes are checked.

- [ ] Human has reviewed **Section 2** (issue list — C1-C5, M1-M10, L1-L4)
- [ ] Human has reviewed **Section 3** (proposed target tree — all (archive), (delete), (move) confirmed)
- [ ] Human has reviewed **Section 4** (Step 2 cleanup plan — OP-2-01 through OP-2-09 confirmed)
- [ ] Human has reviewed **Section 5** (Step 3 refactor plan — relocations, new docs, gate templates confirmed)
- [ ] Human approves proceeding to **Step 2**

> **Sign-off line:** _____________________________ Date: ___________

---

*Document generated by Perplexity AI on 2026-05-05 under Operation Tidy Step 1.*
*HEAD SHA at time of generation: `45e87200a10e4e1af070b9f35d7aacb3580460fb`*
*No existing files were modified in the creation of this document.*
