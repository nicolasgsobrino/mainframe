---
title: Troubleshooting Log
version: "1.0"
---

# TROUBLESHOOTING.md

This is a **living document**. Agents must append a new entry before halting on any failure.
Do not delete entries. Entries are append-only.

> **Housekeeping note (2026-05-05):** File relocated from repo root to `docs/ops/`
> as part of Operation Tidy Commit D (OP-3-04). Content unchanged.

## Entry Format

```yaml
---
id: TS-<sequential number>
date: "YYYY-MM-DD"
phase: <Plan|Build|Validate|Review|Release>
---
```

**Context**: What was the agent doing when this occurred?
**Symptom**: What observable behavior indicated a problem?
**Error Snippet**:
```
<paste exact error output here>
```
**Probable Cause**: Why did this likely occur?
**Quick Fix**: Immediate workaround to unblock.
**Permanent Fix**: Root-cause resolution to implement.
**Prevention**: What rule, test, or check prevents recurrence?

---

## Seeded Entries

---
id: TS-001
date: "2026-04-23"
phase: Build
---

**Context**: Agent resolving Python package dependencies during environment setup.
**Symptom**: `pip install` enters an infinite resolution loop; process does not terminate.
**Error Snippet**:
```
ERROR: Cannot determine installation order for packages; dependency conflict detected.
ResolutionImpossible: for help visit https://pip.pypa.io/en/stable/topics/dependency-resolution/
```
**Probable Cause**: Transitive dependency version conflicts between indirect packages not pinned in `requirements.txt`.
**Quick Fix**: Add a `constraints.txt` file pinning the conflicting indirect dependency to a known-compatible version. Run `pip install -r requirements.txt -c constraints.txt`.
**Permanent Fix**: Audit all direct dependencies with `pip-compile` (pip-tools) to generate a fully-resolved `requirements.txt` with pinned transitive deps. Commit the compiled file.
**Prevention**: Add a CI step that runs `pip check` after install to catch dependency conflicts before they reach the agent environment.

---
id: TS-002
date: "2026-04-23"
phase: Build
---

**Context**: Agent loading a local AI model or embedding model.
**Symptom**: Process killed or Out of Memory (OOM) error during model initialization or inference.
**Error Snippet**:
```
RuntimeError: out of memory. Tried to allocate X GiB.
```
**Probable Cause**: Model size or sequence length exceeds available memory; model loaded in full float32 precision when lower precision is sufficient.
**Quick Fix**: (1) Reduce `batch_size` or context length. (2) Load model with lower precision (e.g., `torch_dtype=torch.float16` or appropriate quantization).
**Permanent Fix**: Profile peak memory usage and document hardware limits in `REPLICATION-NOTES.md`. Ensure inference server is properly configured for the host hardware.
**Prevention**: Add memory guard assertions before large inference calls or pre-flight memory checks.
