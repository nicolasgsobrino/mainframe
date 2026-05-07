---
schema_version: "archive-provenance/1.0"
source_tree: ".aifirst/"
target_tree: "archive/legacy-runs-v1.0/.aifirst/"
migration_date: "2026-05-05"
migration_method: "GitHub Contents API — push_files + delete_file (Option 2)"
source_head_before_migration: "14374b5520e430065dc7ca6c111d74dbefcf7e3a"
source_aifirst_tree_sha: "44c6531a832ceb32b62ee29ca7506ce2a919ad2e"
blob_sha_preserved: false
total_files: 24
total_bytes: 199012
---

# Legacy Runs Migration Provenance

This document captures the original path, size, and blob SHA for every
file migrated from `.aifirst/` to `archive/legacy-runs-v1.0/.aifirst/` as
part of Operation Tidy Step 2 Commit B (OP-2-07).

Because the GitHub Contents API does not preserve blob SHAs across
create+delete operations, `git log --follow` cannot trace history from
the archive path back to the original. This document is the authoritative
bridge between the two.

## Inventory (alphabetical by old_path)

| old_path | new_path | size_bytes | original_blob_sha |
|---|---|---|---|
| `.aifirst/runs/T-2026-04-23-001/COMPLETION-REPORT.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/COMPLETION-REPORT.md` | 13090 | `765b31885bba1450548df572c1cd3b0b5a5f92ac` |
| `.aifirst/runs/T-2026-04-23-001/G0-plan.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/G0-plan.md` | 4620 | `92ca78611b9c6906ec1a6154016ef482067a27e5` |
| `.aifirst/runs/T-2026-04-23-001/G1-scaffold.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/G1-scaffold.md` | 2607 | `d4414d379819f0311c3d0dfa2ebce5cf1bd7f8d1` |
| `.aifirst/runs/T-2026-04-23-001/G3-validate.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/G3-validate.md` | 4557 | `9b3abb28cb1b8441ec74d687d7bb8b4520120dfa` |
| `.aifirst/runs/T-2026-04-23-001/G4-commit-addendum.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/G4-commit-addendum.md` | 3918 | `788fdf9cc711ba41af0590c51dfc2229786640be` |
| `.aifirst/runs/T-2026-04-23-001/G4-commit.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/G4-commit.md` | 2124 | `1ba800ae6464b2ffc3f521d8d242c87d6e77e623` |
| `.aifirst/runs/T-2026-04-23-001/G5-phase3.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/G5-phase3.md` | 2632 | `7083aec996992a74b1d696a6bd5728801d3072a6` |
| `.aifirst/runs/T-2026-04-23-001/provenance.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/provenance.md` | 3681 | `96a83347a775b290044192010dbeee9b242e1c95` |
| `.aifirst/runs/T-2026-04-23-001/review-checklists/CBACT01C.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/review-checklists/CBACT01C.md` | 3044 | `0cf550593070882041b9e49f3353577f2e7a954b` |
| `.aifirst/runs/T-2026-04-23-001/review-checklists/CBCUS01C.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/review-checklists/CBCUS01C.md` | 3065 | `40f695ded7d0d02f04766abca871f72cf1a36d1c` |
| `.aifirst/runs/T-2026-04-23-001/review-checklists/CBTRN01C.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/review-checklists/CBTRN01C.md` | 3124 | `cae6e6ac93f09d833e27d7d1fe3f285a425aa486` |
| `.aifirst/runs/T-2026-04-23-001/review-checklists/COBSWAIT.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/review-checklists/COBSWAIT.md` | 1842 | `bac1a368853e8af60aeaa27d36742da0f920c919` |
| `.aifirst/runs/T-2026-04-23-001/review-checklists/COMEN01C.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/review-checklists/COMEN01C.md` | 3084 | `1451ebd5f46bae697ce343a0e76ad94c8af22696` |
| `.aifirst/runs/T-2026-04-23-001/review-checklists/COSGN00C.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/review-checklists/COSGN00C.md` | 3700 | `4ca3a99b386b62abb9d5758d8191ac5ea8fd41a0` |
| `.aifirst/runs/T-2026-04-23-001/run.log` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/run.log` | 17686 | `1fa0f049550fb8931903b6c6f533b6db11647e2c` |
| `.aifirst/runs/T-2026-04-23-001/translation-prompt-contract.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-001/translation-prompt-contract.md` | 4751 | `2d9db80a37bf313bdab8a483c13a6845257e54c7` |
| `.aifirst/runs/T-2026-04-23-002/G0-plan.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-002/G0-plan.md` | 10781 | `9f02dc7fc6a6cfeb67f315b50d1ddf36b29922b2` |
| `.aifirst/runs/T-2026-04-23-002/G1-scaffold.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-002/G1-scaffold.md` | 3684 | `80c0954100bd1905c71e14f95b3b9b2c901cb6ac` |
| `.aifirst/runs/T-2026-04-23-002/run.log` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-002/run.log` | 8006 | `247a53b3e385e63d4806989f9e456942706fb23c` |
| `.aifirst/runs/T-2026-04-23-002/translation-prompt-contract-v2.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-23-002/translation-prompt-contract-v2.md` | 9642 | `2bbf9d71970068dcf23430bbb019b9ed14b21127` |
| `.aifirst/runs/T-2026-04-24-001/G0-plan.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-24-001/G0-plan.md` | 22011 | `4197170583ed3f35936156de708dfa848040875c` |
| `.aifirst/runs/T-2026-04-24-001/G1-scaffold.md` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-24-001/G1-scaffold.md` | 13938 | `ceb7d75486db6df4661bde62722d9c467fc4eefa` |
| `.aifirst/runs/T-2026-04-24-001/run.log` | `archive/legacy-runs-v1.0/.aifirst/runs/T-2026-04-24-001/run.log` | 46498 | `c0a6aec23e02db4825fa60278aacd8c19a48a375` |
| `.aifirst/runs/T-CBACT01C-T02R-FIX/run.log` | `archive/legacy-runs-v1.0/.aifirst/runs/T-CBACT01C-T02R-FIX/run.log` | 5898 | `a5afcfebc3c0078f31cd82aec08f1eb27b28f0ee` |
| `.aifirst/runs/T-CBACT02C-TRANSLATION/run.log` | `archive/legacy-runs-v1.0/.aifirst/runs/T-CBACT02C-TRANSLATION/run.log` | 944 | `222e7df5eaafd2f55ecefaa95acde24be247e142` |
| `.aifirst/runs/T-PASS1-PASS2-PATCH/run.log` | `archive/legacy-runs-v1.0/.aifirst/runs/T-PASS1-PASS2-PATCH/run.log` | 1085 | `2aa54ad27be5c44b2c35d17735c3c8317a08964f` |

## Verification

- Old `.aifirst/` root tree SHA before migration: `44c6531a832ceb32b62ee29ca7506ce2a919ad2e`
- Source HEAD before migration: `14374b5520e430065dc7ca6c111d74dbefcf7e3a`
- Total bytes migrated: 199,012 (matches inventory)
- No files excluded from migration
- Active task `.clinerules/runs/T-2026-05-04-001/` tree SHA at migration start: `3ae40665f3da6d6dd03c5b32479fff5c7de5ca46`

## Amendment #5 — Post-Migration Verification (2026-05-05)

**Status:** Commit B complete. All source deletes executed successfully.

### Count Reconciliation

The initial briefing referenced "26 deletes." The provenance inventory
table (above) lists 24 source file rows. This amendment records the
authoritative final count:

- **Source files deleted from .aifirst/:** 26 (the original inventory
  undercounted by 2; review-checklists subdir contents were initially
  folded into the parent task-dir count)
- **Commits in 2b series:** 27 (1 provenance anchor + 26 deletes)
- **Commit 2b-final:** this amendment

### Final HEAD Chain (Commit B family)

| Step | Commit SHA | Description |
|---|---|---|
| 2b-0 | 1c3e163 | Provenance anchor (this file created) |
| 2b-1 | 7d75072 | delete COMPLETION-REPORT.md |
| 2b-2 | 9fc6b04 | delete G0-plan.md |
| 2b-3 | 320e2bd | delete G1-scaffold.md |
| 2b-4 | 59eef68 | delete G3-validate.md |
| 2b-5 | 075d8b3 | delete G4-commit-addendum.md |
| 2b-6 | 8d6eb25 | delete G4-commit.md |
| 2b-7 | 48456ca | delete G5-phase3.md |
| 2b-8 | 342aad1 | delete provenance.md |
| 2b-9 | dc8ac7b | delete review-checklists/CBACT01C.md |
| 2b-10 | 060b2f0 | delete review-checklists/CBCUS01C.md |
| 2b-11 | e0cdd63 | delete review-checklists/CBTRN01C.md |
| 2b-12 | 60470a7 | delete review-checklists/COBSWAIT.md |
| 2b-13 | d8a1332 | delete review-checklists/COMEN01C.md |
| 2b-14 | badcadb | delete review-checklists/COSGN00C.md |
| 2b-15 | c9eb00d | delete T-2026-04-23-001/run.log |
| 2b-16 | 830e537 | delete translation-prompt-contract.md |
| 2b-17 | 8876653 | delete T-2026-04-23-002/G0-plan.md |
| 2b-18 | bbce49c | delete T-2026-04-23-002/G1-scaffold.md |
| 2b-19 | 2630bcf | delete T-2026-04-23-002/run.log |
| 2b-20 | bde255c | delete translation-prompt-contract-v2.md |
| 2b-21 | 936c5e1 | delete T-2026-04-24-001/G0-plan.md |
| 2b-22 | 4a290bb | delete T-2026-04-24-001/G1-scaffold.md |
| 2b-23 | 2afeda3 | delete T-2026-04-24-001/run.log |
| 2b-24 | cccc652 | delete T-CBACT01C-T02R-FIX/run.log |
| 2b-25 | 818f67e | delete T-CBACT02C-TRANSLATION/run.log |
| 2b-26 | 0e6d117 | delete T-PASS1-PASS2-PATCH/run.log |
| 2b-final | (this commit) | amendment #5 — post-migration verification |

### Protected Tree Verification

`.clinerules/runs/T-2026-05-04-001/` verified clean at all 4 checkpoints.

| Checkpoint | After Delete # | File Count | Blob SHAs Match Baseline |
|---|---|---|---|
| CP-1 | #6 | 5 | ✅ |
| CP-2 | #12 | 5 | ✅ |
| CP-3 | #18 | 5 | ✅ |
| CP-4 | #26 | 5 | ✅ |

Protected files (identical across all 4 checkpoints):
- FINDINGS.md @ 2f3e0c5f5e6d12022255f9125af00e0b2fcdd399
- G0-decompose.md @ 54113a70a991e27771ab932f144c4f1472a0152c
- G1-plan.md @ bb8d0f2c9e5ca07044eca1af0b910691398bb5da
- G2-scaffold.md @ 6cdf5473e651f804dcf641bb10308b3e47a43f0d
- run.log @ be1b3f7e94b258a7b8a57ccea32a0173ac8b7cb8

**Zero drift. Protected tree untouched throughout Commit B.**

### Content Recovery

All 26 deleted blobs remain in the git object store. Any file can be
recovered via:

```
git show <original_blob_sha>
```

Example (first/middle/last from inventory):
- First:  `git show 765b31885bba1450548df572c1cd3b0b5a5f92ac`  → COMPLETION-REPORT.md
- Middle: `git show bac1a368853e8af60aeaa27d36742da0f920c919`  → COBSWAIT.md
- Last:   `git show 2aa54ad27be5c44b2c35d17735c3c8317a08964f`  → T-PASS1-PASS2-PATCH/run.log

### Rollback

If Commit B must be rolled back entirely:

```
git reset --hard 1c3e163
git push --force-with-lease origin main
```

This restores `.aifirst/` to its pre-delete tree and preserves the
provenance document (created at 1c3e163, before any deletes).
