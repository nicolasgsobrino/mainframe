# archive/ — Operation Tidy Archive Index

> **Generated:** 2026-05-05 | **Operation:** OPERATION-TIDY | **Step:** Commit D (OP-3-17)
> **Purpose:** Permanent record of archived material — what was archived, why, and from which commit.

This directory contains artifacts removed from active paths during Operation Tidy.
All contents are **read-only historical references**. Do not edit or delete entries.
Do not add new subdirectories here without updating this index.

---

## Archive Index

| Subdirectory | Original Path | Archived In | Reason | Original Commit SHA |
|---|---|---|---|---|
| `archive/protocol-v1.0/` | Root `AiFirst Protocol — Master Specification & Gate Templates.md` | Commit B (Step 2) | Stale v1.0 root duplicate — canonical is `.clinerules/00-aifirst-protocol.md` v2.1 | `a198dc7` |
| `archive/protocol-v1.0/gates/` | `.clinerules/protocol/gates/G0-G4.template.md` (5 files) | Commit B (Step 2) | v1.0 gate templates superseded by v2.1 schema (6 gates, renamed G0-G5) | `a198dc7` |
| `archive/legacy-runs-v1.0/` | `.aifirst/` (entire legacy run store) | Commit B (Step 2) | v1.0 run store — canonical run store is `.clinerules/runs/T-YYYY-MM-DD-NNN/` | `a198dc7` |
| `archive/translations-baseline-v1.2/` | `translations/baseline-v1.2/` | Commit B (Step 2) | 4th translation copy tier with no pipeline role; versioning via git tags only | `a198dc7` |
| `archive/translations-tier-review/gold/` | `translations/gold/` | Commit B (Step 2) | Stub tier (1 file); tier under review — COBSWAIT.md active copy in gold-candidate | `a198dc7` |

---

## Recovery Instructions

To restore any archived file:
```bash
git log --all --full-history -- archive/<path>   # find the archive commit
git show <commit-sha>:archive/<path>             # view content without checkout
git checkout <commit-sha> -- archive/<path>      # restore to working tree
```

All original content is preserved in git history and accessible via the commit SHA column above.

---

*Maintained by Operation Tidy. Last updated: 2026-05-05.*
