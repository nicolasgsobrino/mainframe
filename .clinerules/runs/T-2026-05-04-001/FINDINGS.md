---
schema_version: "aifirst-findings/1.0"
task_id: "T-2026-05-04-001"
program_id: "CBCUS01C"
---

# Findings Ledger — T-2026-05-04-001 CBCUS01C

## Finding F-001 — Corpus-wide doctor errors (out-of-scope for CBCUS01C)
- Type: corpus health / structural anomaly
- Severity: medium (not blocking CBCUS01C; blocking corpus readiness)
- Location: multiple programs across validation/ corpus (16 errors, 8 warnings)
- Description: syncd doctor exit 2; errors all in programs other than CBCUS01C
- Evidence: terminal-G2.log syncd doctor output at 2026-05-05T12:04Z
- Impact on CBCUS01C: None direct; CBCUS01C itself has only stale source_sha warning
- Impact on corpus: Significant; future tasks will be blocked until triaged
- Surfaced at: G2, T-2026-05-04-001
- Surfaced by: qwen3-coder-next-80b
- Next action: separate tidy task (TBD)