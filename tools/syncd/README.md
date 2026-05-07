# syncd v1.1

Manifest-driven pipeline sync tool for the COBOL-MD-PIPELINE.
Locks verified CFG numbers into `SYNC-MANIFEST.yaml` so every agent
and PR can confirm they are working from the same ground truth.

## Requirements

- Python 3.10+
- PyYAML (`pip install pyyaml`)
- Jinja2 (`pip install jinja2`) — required for `scaffold` only
- `gh` CLI — required for `bundle --pr` only

## Commands

### `status` — show branch + manifest summary

```powershell
py tools/syncd/sync.py status
```

Example output:

```
============================================================
syncd v1.1 -- status
============================================================
  Branch : wave1/cbstm03a
  HEAD   : cecae47f6a7b37da647d4fba159f0df46ad9e527
  Manifest: C:\...\SYNC-MANIFEST.yaml
  Schema  : syncd/1
  Programs locked: 1

  PROGRAM              PARAGRAPHS    L01 LOCKED_AT
  -------------------- ---------- ------ ------------------------
  CBSTM03A                     25     18 2026-05-04T01:00:00Z
```

---

### `lock <PROGRAM>` — lock CFG numbers into manifest

Reads `validation/structure/<PROGRAM>_cfg.json`, extracts paragraph
and L01 counts, verifies against `extract_ground_truth.py` output,
and writes a `locked_numbers` block into `SYNC-MANIFEST.yaml`.
Idempotent — safe to re-run after any CFG update.

```powershell
py tools/syncd/sync.py lock CBSTM03A
# [syncd] LOCKED CBSTM03A: 25 paragraphs, 18 L01 items
```

---

### `verify` — run all three pipeline health checks

Runs `gate_compare.py`, `lint_cobol.py --fail-on-error`, and
`extract_md_claims.py` in sequence. Exits `0` only if all three pass.

```powershell
py tools/syncd/sync.py verify
# [syncd] Running gate_compare.py ...
# [syncd] Running lint_cobol.py --fail-on-error ...
# [syncd] Running extract_md_claims.py ...
# [syncd] VERIFY PASS -- all checks clean
```

---

### `promote <PROGRAM>` — run pipeline stages 0-GT then lock

Runs `normalize_rekt_output.py` (if present), `extract_cfg_summary.py`,
`extract_ground_truth.py`, then locks the manifest. Does **not** run
the MD generator.

```powershell
py tools/syncd/sync.py promote CBSTM03A
# [syncd] Running extract_cfg_summary.py CBSTM03A ...
# [syncd] Running extract_ground_truth.py ...
# [syncd] LOCKED CBSTM03A: 25 paragraphs, 18 L01 items
# [syncd] PROMOTE CBSTM03A complete -- manifest locked
# [syncd] Next step: write translations/gold-candidate/CBSTM03A.md (human + agent)
```

---

### `scaffold <PROGRAM> [--force]` — generate .md skeleton  *(v1.1)*

Generates `translations/gold-candidate/<PROGRAM>.md` with correct
frontmatter (from manifest locked numbers + CFG), all paragraph stubs,
all data_item stubs, and TODO markers for human/agent fill-in.

**Refuses to overwrite an existing `.md` unless `--force` is passed.**

```powershell
# First-time generation
py tools/syncd/sync.py scaffold CBSTM03A
# [syncd] SCAFFOLD CBSTM03A -> translations/gold-candidate/CBSTM03A.md
# [syncd] Paragraphs: 25 | L01: 18 | Dead: 0 | goto_flag: True
# [syncd] Edit TODO markers, then run: py tools/syncd/sync.py verify

# Overwrite after re-locking
py tools/syncd/sync.py scaffold CBSTM03A --force
```

Exit codes:
- `0` — scaffold written
- `2` — locked_numbers missing from manifest (run `lock` first)
- `3` — file exists and `--force` not passed

---

### `doctor` — full health check  *(v1.1)*

Runs five checks and reports warnings/errors:

| Check | What it detects |
|---|---|
| a. Forbidden paths | Staged/modified files under `validation/`, `translations/`, `app/`, `.clinerules/` |
| b. Manifest vs CFG | Paragraph and L01 count drift; stale `cfg_sha` |
| c. Truncation | `"000-"` / `"999-"` leading-zero truncation in any `structure/*_cfg.json` |
| d. Source SHA | Stale `source_sha` in any `.md` frontmatter |
| e. Git status | Modified files in working tree |

```powershell
py tools/syncd/sync.py doctor
# ============================================================
# syncd doctor
# ============================================================
#   [OK] All checks passed

# Or with issues:
#   [WARN]  CBSTM03A: cfg_sha in manifest (d1665343...) differs from current (abcd1234...)
#   [ERROR] FORBIDDEN PATH in working tree/index: validation/gate_compare.py
```

Exit codes:
- `0` — clean
- `1` — warnings only
- `2` — one or more errors
- `3` — forbidden path write detected

---

### `bundle <PROGRAM> [--pr]` — verify, stage, commit  *(v1.1)*

Runs `verify`, stages exactly these 4 files, and commits with a
standard message. Refuses to proceed if anything else is staged.

Allowed files:
- `translations/gold-candidate/<PROGRAM>.md`
- `validation/structure/<PROGRAM>_cfg.json`
- `SYNC-MANIFEST.yaml`
- `validation/lint_cobol/lint_results/lint_results.json`

```powershell
# Commit only
py tools/syncd/sync.py bundle CBSTM03A

# Commit + open PR via gh CLI
py tools/syncd/sync.py bundle CBSTM03A --pr
```

Example commit message:
```
feat(trust): CBSTM03A gold-candidate — gate PASS via syncd

Locked numbers: 25 paragraphs / 18 L01 items
Source SHA: ea341ec97f2b1a236de57f9c0fbd262f61b23511
Verified by: syncd verify (gate_compare + lint_cobol + extract_md_claims)
```

Exit codes:
- `0` — committed (and PR created if `--pr`)
- `1` — verify failed or commit failed
- `3` — extra files found in git index

---

## Write Safety

`sync.py` enforces a forbidden-path check on every file write.
The only paths it will ever write to are:

- `SYNC-MANIFEST.yaml`
- `tools/syncd/` (its own directory)
- `translations/gold-candidate/` (scaffold output only)

Any attempt to write elsewhere exits with code `3`.

---

## Schema

`tools/syncd/manifest_schema.json` is a JSON Schema (draft-07)
document for `SYNC-MANIFEST.yaml`. Validate with:

```powershell
py -c "
import json, yaml, jsonschema
schema = json.load(open('tools/syncd/manifest_schema.json'))
data   = yaml.safe_load(open('SYNC-MANIFEST.yaml'))
jsonschema.validate(data, schema)
print('VALID')
"
```

---

## Typical Wave Workflow

```powershell
# 1. After REKT runs and CFG JSON is committed:
py tools/syncd/sync.py promote CBSTM03A

# 2. Generate skeleton .md:
py tools/syncd/sync.py scaffold CBSTM03A

# 3. Fill in TODO markers (human + agent)

# 4. Health check before commit:
py tools/syncd/sync.py doctor

# 5. Bundle and commit:
py tools/syncd/sync.py bundle CBSTM03A

# 6. Optional: open PR:
py tools/syncd/sync.py bundle CBSTM03A --pr
```
