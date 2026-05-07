---
title: Replication Notes
version: "1.0"
---

# REPLICATION-NOTES.md

This document enables a fresh operator to reproduce the environment exactly.
Agents must append entries before halting. Entries are append-only.

> **Housekeeping note (2026-05-05):** File relocated from repo root to `docs/ops/` as part of Operation Tidy Commit D (OP-3-03). Content unchanged.

## Replicable Setup Checklist

```yaml
checklist:
  - step: "Clone repository"
    command: "git clone <repo-url> && cd <repo-name>"
  - step: "Create Python virtual environment"
    command: "python -m venv .venv && source .venv/bin/activate  # Linux/Mac"
    windows: ".venv\\Scripts\\Activate.ps1"
  - step: "Install dependencies with constraints"
    command: "pip install -r requirements.txt -c constraints.txt"
  - step: "Verify AI model connectivity"
    command: "Verify local or API-based inference server is running and accessible."
  - step: "Confirm Qwen3.6 35B A3B loaded"
    check: "Ensure the baseline model is active and responding to test prompts."
  - step: "Run validation gates"
    command: "pytest -q && ruff check . && mypy ."
    pass_condition: "All green"
```

## AI Model & Environment Notes

```yaml
environment:
  workflow: "Hardware and AI agnostic (designed for local or cloud replication)"
  baseline_model: "Qwen3.6 35B A3B (used for 1:1 COBOL to MD quality validation before fine-tuning)"
  framework: "Cline in VSCode with AiFirst Gated Protocol"
```

## Known Pitfalls to Avoid Next Run

1. **Model Context Limits** — Ensure the context window of the configured model is large enough for the target file sizes. Enable truncation or chunking if processing large legacy files.
2. **Pin indirect dependencies** — see TS-001. `requirements.txt` alone is insufficient for reproducible installs.
3. **Floating Point Precision** — If running local inference, loading embedding models in full precision (fp32) may cause OOM. Use fp16 where supported.

## Recurring Errors

| ID | Error | Resolution | Frequency |
|----|-------|------------|-----------|
| TS-001 | Dependency resolution loop | `constraints.txt` pin | Seen on fresh env setup |
| TS-002 | Embedding OOM | fp16 + batch reduction | Seen on first model load |

## Environment Deltas

_Append entries here when the environment changes (package updates, hardware changes, model version bumps)._

| Date | Delta | Impact |
|------|-------|--------|
| 2026-04-23 | Baseline generic setup — Cline, Qwen3.6 35B A3B | Baseline |
