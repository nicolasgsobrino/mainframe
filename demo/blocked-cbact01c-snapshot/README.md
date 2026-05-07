# BLOCKED Snapshot — CBACT01C

> **Task ID:** `T-2026-04-27-001`
> **Gate:** G3 (VALIDATE) — BLOCKED
> **Branch:** `demo/blocked-cbact01c-snapshot`
> **Tag:** `demo-snapshot-v1`
> **Created:** 2026-04-27

## Why This Snapshot Exists

`CBACT01C` (Account Activity processor) failed Gate 3 validation during the pilot translation run.
The translation was **BLOCKED** — it did not pass all validation tiers — and the code was never merged
into `main`. This snapshot preserves the BLOCKED state so it can be referenced, audited, or
reopened in a future task without losing the original artifacts.

## What Is Included

| Artifact | Source Path | Description |
|----------|-------------|-------------|
| `CBACT01C.cbl` | `app/cbl/CBACT01C.cbl` | Original COBOL source |
| `CBACT01C.md` | `translations/baseline/CBACT01C.md` | Generated Markdown translation (v12) |
| `CBACT01C_T01.json` | `validation/reports/CBACT01C_T01.json` | Schema validity report |
| `CBACT01C_T02.json` | `validation/reports/CBACT01C_T02.json` | Structural correctness report |
| `CBACT01C_T02R.json` | `validation/reports/CBACT01C_T02R.json` | T02R postfix pass report |
| `CBACT01C_T03.json` | `validation/reports/CBACT01C_T03.json` | Functional output report |
| `CBACT01C_T04.json` | `validation/reports/CBACT01C_T04.json` | Semantic accuracy report |
| `CBACT01C_v12_T01.json` | `validation/reports/CBACT01C_v12_T01.json` | v12 schema report |
| `CBACT01C_v12_T02.json` | `validation/reports/CBACT01C_v12_T02.json` | v12 structural report |
| `CBACT01C_v12_T03.json` | `validation/reports/CBACT01C_v12_T03.json` | v12 functional report |

## Block Reason

The translation of `CBACT01C.cbl` → `CBACT01C.md` was evaluated against the AiFirst protocol
validation tiers (T01–T05). One or more tiers failed, causing the gate to be set to **BLOCKED**.

To reopen this translation:

1. Create a new task (e.g., `T-YYYY-MM-DD-NNN`) referencing this snapshot.
2. Review the validation reports above to understand what failed.
3. Re-run the translation pipeline with corrections.
4. Pass all G3 tiers before proceeding to G4 (COMMIT).

## Git History

```
Branch: demo/blocked-cbact01c-snapshot
Parent: 88ebfd0 (main)
Tag:    demo-snapshot-v1