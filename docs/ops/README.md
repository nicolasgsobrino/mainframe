# docs/ops/ — Operational Documents

> **Created:** 2026-05-05 | **Operation:** OPERATION-TIDY | **Step:** Commit D (OP-3-13)

This directory contains operational planning and reference documents for the
aws-mainframe-modernization-carddemo project. These files were previously
scattered at the repository root and were relocated here as part of Operation Tidy
(OP-3-07, OP-3-08 per OPERATION-TIDY-PLAN.md).

---

## Contents

| File | Purpose | Status |
|---|---|---|
| `DEMO-SPRINT-PLAN.md` | Demo completion sprint — Track 1 (Code), Track 2 (Language), Track 3 (Rehearsal) | Active — Tracks 2–3 pending |
| `PATCH-PLAN.md` | Pass 1/Pass 2 ambiguity patch plan — P1–P5 all merged to main | Complete (all 5 patches merged 2026-04-30) |
| `REPLICATION-NOTES.md` | Environment replication checklist + known pitfalls | Living document — append-only |
| `TROUBLESHOOTING.md` | Troubleshooting log with seeded entries TS-001/TS-002 | Living document — append-only |

---

## Maintenance

- **Owner:** MrSnowNB
- **Policy:** Operational documents here are living documents. Agents must append
  entries to `REPLICATION-NOTES.md` and `TROUBLESHOOTING.md` before halting on any
  failure. Do not delete entries from those two files.
- **DEMO-SPRINT-PLAN.md** and **PATCH-PLAN.md** are historical/completed plans;
  update status checkboxes only, do not restructure.

---

*Maintained by Operation Tidy. Last updated: 2026-05-05.*
