---
schema_version: "archive-provenance/1.0"
source_trees:
  - "translations/baseline-v1.2/"
  - "translations/gold/"
target_tree: "none — delete-only per Path 3"
migration_date: "2026-05-05"
migration_method: "Contents API DELETE only; content preserved in git object store"
source_head_before_migration: "524eabdd3288274e5a9d623ea129e1945c73bd26"
blob_sha_preserved: "N/A — Path 3 delete-only, blobs remain in git object store"
total_files: 8
total_bytes: 437581
---

# Translations Archive Provenance

This document records the original path, size, and blob SHA for every
file deleted from `translations/baseline-v1.2/` (OP-2-08) and
`translations/gold/` (OP-2-09) as part of Operation Tidy Step 2 Commit C.

**Path 3 — delete-only.** No content was copied to `archive/`.
All deleted blobs remain permanently in the git object store.
This document is the authoritative recovery bridge.

## OP-2-08 Inventory — translations/baseline-v1.2/

| old_path | size_bytes | blob_sha |
|---|---|---|
| `translations/baseline-v1.2/.gitkeep` | 0 | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` |
| `translations/baseline-v1.2/CBACT01C.md` | 83593 | `bb4594377248892c374cff4f0ee5cafe6c56993f` |
| `translations/baseline-v1.2/CBCUS01C.md` | 35932 | `45d1807cf9465f61f6a090d9fc92ceea7f561bda` |
| `translations/baseline-v1.2/CBTRN01C.md` | 80298 | `a864a80420064ee5f31c3f84bb4aad35929116d4` |
| `translations/baseline-v1.2/COBSWAIT.md` | 5776 | `cf9b2f4d8c9da6b338d4e5a467c7c684cb1563b1` |
| `translations/baseline-v1.2/COMEN01C.md` | 135924 | `25a6ab300da71e90fafd0906dc9bb30e5c584b11` |
| `translations/baseline-v1.2/COSGN00C.md` | 91429 | `e049b845ffb08fbaecdebd48dad58d440b8b5317` |

**Subtotal OP-2-08:** 7 files, 432,952 bytes

## OP-2-09 Supplementary Deletion — translations/gold/

The `translations/gold/` tier contained a single file, representing an
abandoned or incomplete promotion from `gold-candidate/`. Per M2 in the
tidy plan, this stub tier is archived rather than preserved in-tree.

| old_path | size_bytes | blob_sha |
|---|---|---|
| `translations/gold/COBSWAIT.md` | 4629 | `21e6845d3cfc70c1eca805f26f8f906faa42aea2` |

**Subtotal OP-2-09:** 1 file, 4,629 bytes

**Grand total:** 8 files, 437,581 bytes

## Content Recovery

All deleted blobs remain in the git object store. Recover any file via:

```
git show <blob_sha>
```

Examples:
- First:  `git show bb4594377248892c374cff4f0ee5cafe6c56993f`  → CBACT01C.md
- Middle: `git show cf9b2f4d8c9da6b338d4e5a467c7c684cb1563b1`  → COBSWAIT.md
- Last:   `git show 21e6845d3cfc70c1eca805f26f8f906faa42aea2`  → translations/gold/COBSWAIT.md

## Verification

- Source HEAD before deletions: `524eabdd3288274e5a9d623ea129e1945c73bd26`
- Active task `.clinerules/runs/T-2026-05-04-001/` tree SHA at migration start: `3ae40665f3da6d6dd03c5b32479fff5c7de5ca46`
- Total bytes deleted: 437,581 (matches inventory)
- No files excluded from deletion

## Rollback

If Commit C must be rolled back entirely:

```
git reset --hard 05880aa66afd4fe2809e1f99f6f5a392f259b087
git push --force-with-lease origin main
```

C-0 SHA: `05880aa66afd4fe2809e1f99f6f5a392f259b087`

This restores `translations/baseline-v1.2/` and `translations/gold/` to
their pre-delete state while preserving this provenance document.

---

## Amendment — Post-Migration Verification (2026-05-05)

**Status:** Commit C complete. All source deletes executed successfully.

### Full Commit C Chain

| Step | Commit SHA | Description |
|---|---|---|
| C-0 | 05880aa66afd4fe2809e1f99f6f5a392f259b087 | Provenance anchor (this file created) |
| C-1 | 4a6f1fd79cf82ce6c7a1b7758cf5691db9acfc83 | delete translations/baseline-v1.2/.gitkeep |
| C-2 | 3406b8bc8f775ca736cc91b243fc2d0444ebea02 | delete translations/baseline-v1.2/CBACT01C.md |
| C-3 | 0785b2c583b4770a54f2b9493c188b0cf9ee9be7 | delete translations/baseline-v1.2/CBCUS01C.md |
| C-4 | 8edc0ac01ef543c66411243ee9fe2383af4e77fd | delete translations/baseline-v1.2/CBTRN01C.md |
| C-5 | 85f61f9e4c01b27c92fdaa7206a8a759e66eb10e | delete translations/baseline-v1.2/COBSWAIT.md |
| C-6 | f081c7d11be4c8b3535cb6024be819884b0bc545 | delete translations/baseline-v1.2/COMEN01C.md |
| C-7 | 82cb25207828aadeceec288c21b7152893549a7d | delete translations/baseline-v1.2/COSGN00C.md |
| C-8 | cc7cef883d3b7b85ea3393c75130476f590c6127 | delete translations/gold/COBSWAIT.md |
| C-final | (this commit) | amendment — post-migration verification |

### Protected Tree Verification

`.clinerules/runs/T-2026-05-04-001/` verified clean at all 3 checkpoints.

| Checkpoint | After Delete # | File Count | Blob SHAs Match Baseline |
|---|---|---|---|
| CP-1 | #3 | 5 | ✅ |
| CP-2 | #7 | 5 | ✅ |
| CP-3 | #8 | 5 | ✅ |

Protected files (identical across all 3 checkpoints):
- FINDINGS.md @ 2f3e0c5f5e6d12022255f9125af00e0b2fcdd399
- G0-decompose.md @ 54113a70a991e27771ab932f144c4f1472a0152c
- G1-plan.md @ bb8d0f2c9e5ca07044eca1af0b910691398bb5da
- G2-scaffold.md @ 6cdf5473e651f804dcf641bb10308b3e47a43f0d
- run.log @ be1b3f7e94b258a7b8a57ccea32a0173ac8b7cb8

**Zero drift. Protected tree untouched throughout Commit C.**

### Spot-Check Blob Recovery

- First:  `git show bb4594377248892c374cff4f0ee5cafe6c56993f`  → CBACT01C.md (83,593 bytes)
- Middle: `git show cf9b2f4d8c9da6b338d4e5a467c7c684cb1563b1`  → COBSWAIT.md (5,776 bytes)
- Last:   `git show 21e6845d3cfc70c1eca805f26f8f906faa42aea2`  → translations/gold/COBSWAIT.md (4,629 bytes)
