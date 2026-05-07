---
manifest_type: tool-chain
tool_id: structural-gate
version: "1.0"
description: >
  Deterministic structural gate: validates gold-candidate MD translations
  against Cobol-REKT CFG ground truth. No LLM in the validation path.
  Run after any MD edit or CFG change.

prereqs:
  - cmd: python validation/extract_ground_truth.py
    description: Normalize CFG JSON into gate-comparable ground truth
    input_glob: validation/structure/{PROGRAM}_cfg.json
    output_glob: validation/ground_truth/{PROGRAM}_gt.json
    exit_on_fail: true

  - cmd: python validation/extract_md_claims.py
    description: Parse MD frontmatter YAML into claims JSON
    input_glob: translations/gold-candidate/{PROGRAM}.md
    output_glob: validation/claims/{PROGRAM}_claims.json
    exit_on_fail: true

invoke:
  cmd: python validation/gate_compare.py
  description: Diff ground truth vs claims, emit gate report
  input_glob: "validation/ground_truth/{PROGRAM}_gt.json + validation/claims/{PROGRAM}_claims.json"
  output_glob: validation/reports/{PROGRAM}_gate.json
  exit_contract:
    success: 0
    failure: 1

single_program_override:
  pattern: "python validation/{script}.py {PROGRAM}"
  example: python validation/gate_compare.py CBACT01C

programs:
  - CBACT01C
  - CBCUS01C
  - CBTRN01C
  - COBSWAIT
  - COMEN01C
  - COSGN00C

does:
  - Checks all 8 structural properties of an MD translation against source CFG
  - Emits per-program JSON gate reports with pass/fail/warning detail
  - Accepts synthetic paragraph labels for inline-only programs (synthetic: true)
  - Exits 0 only when every targeted program passes all checks
  - Works on any machine with Python 3.8+ and pyyaml; no network, no LLM

does_not:
  - Read or evaluate MD prose body (frontmatter YAML only)
  - Score semantic quality (that is T04 judge scope)
  - Modify any source .cbl or CFG JSON file
  - Run T02/T03/T04/T05 validation tiers
  - Auto-fix failing programs
  - Require Cobol-REKT to be installed locally (CFG JSONs are pre-committed)

failure_means:
  - The MD frontmatter makes a structural claim the CFG cannot support
  - Fix the MD, re-run extract_md_claims.py, re-run gate_compare.py
  - Do NOT edit CFG JSONs or .cbl source to make a failing gate pass

harness_invocation: |
  # Load this manifest
  import yaml, pathlib
  manifest = yaml.safe_load(pathlib.Path("validation/README-gate.md").read_text().split("---")[1])
  # Execute prereqs in order, then invoke
  for step in manifest["prereqs"]:
      run(step["cmd"])   # exit_on_fail honoured per step
  run(manifest["invoke"]["cmd"])
  # Gate passes if exit code == manifest["invoke"]["exit_contract"]["success"]
---

# Structural Gate Pipeline — Block F

Three deterministic scripts that verify gold-candidate `.md` translations
against Cobol-REKT CFG ground truth. **No LLM in the validation path.**

## Prerequisites

```powershell
pip install pyyaml   # only external dependency
```

All 6 CFG JSONs must exist in `validation/structure/`:
- `CBACT01C_cfg.json`
- `CBCUS01C_cfg.json`
- `CBTRN01C_cfg.json`
- `COBSWAIT_cfg.json`
- `COMEN01C_cfg.json`
- `COSGN00C_cfg.json`

## Run Order

```powershell
# Step 1 — build ground truth from CFG JSONs (run once per source change)
python validation/extract_ground_truth.py

# Step 2 — extract structural claims from MD files
python validation/extract_md_claims.py

# Step 3 — diff and gate
python validation/gate_compare.py
```

Or run a single program:
```powershell
python validation/extract_ground_truth.py CBACT01C
python validation/extract_md_claims.py CBACT01C
python validation/gate_compare.py CBACT01C
```

## Outputs

| Script | Output location |
|--------|-----------------|
| `extract_ground_truth.py` | `validation/ground_truth/{PROGRAM}_gt.json` |
| `extract_md_claims.py` | `validation/claims/{PROGRAM}_claims.json` |
| `gate_compare.py` | `validation/reports/{PROGRAM}_gate.json` |

Exit code `0` = all programs passed. Exit code `1` = failures present.

## Gate Checks

| Check | Severity | Description |
|-------|----------|-------------|
| `paragraphs_missing_from_md` | FAIL | Reachable source paragraph absent from MD |
| `hallucinated_paragraphs` | FAIL | MD claims paragraph not in source or dead-code list |
| `data_items_missing` | FAIL | Level-01 source item absent from MD |
| `data_items_hallucinated` | FAIL | Level-01 MD item not in source |
| `redefines_missing` | FAIL | REDEFINES clause not declared in MD |
| `calls_missing` | FAIL | CALL target absent from MD |
| `copybooks_missing` | FAIL | COPY statement absent from MD |
| `fabricated_t04_score` | FAIL | `t04_semantic_score` is non-null without a judge report |
| `dead_code_not_declared_in_md` | WARNING | CFG dead paragraph not marked `reachable: false` in MD |
| `synthetic_paragraphs_accepted` | INFO | Inline-only program; MD synthetic labels accepted |

## Adding a New Program

1. Ensure `validation/structure/{NEWPROG}_cfg.json` exists
2. Add `NEWPROG` to the `PROGRAMS` list in all three scripts
3. Run the three-step pipeline

No other changes required.

## Anti-Hallucination Note

The `fabricated_t04_score` check was added after Block F experiment
`experiment/block-f-cline-hallucination-study` (tag SHA `e1f6d9f`)
demonstrated that a translation agent wrote `t04_semantic_score: 0.89`
to its own output with no judge process having run.

`t04_semantic_score` MUST remain `null` until `validation/reports/{PROGRAM}_T04_judge.json`
exists and `gate_compare.py` reads the score from that file — never from the MD itself.
