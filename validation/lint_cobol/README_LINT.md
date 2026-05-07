# Layer 2 — COBOL Source Lint Framework

## Architecture Placement

```
Layer 1 — Source (authoritative)
  app/cbl/*.cbl          Raw IBM COBOL source — this IS the truth
  app/cpy/*.cpy          Copybooks

Layer 2 — Static Analysis (deterministic, local)       ← YOU ARE HERE
  lint_cobol/            Pre-analysis source lint       ← NEW
    lint_cobol.py        Runner — scans all app/cbl/*.cbl
    rules/L001_*.py      Lint rules (one file per rule)
    lint_results/        Generated findings (gitignored at runtime)
  Cobol-REKT             Paragraph CFG extractor  → validation/rekt/
  GnuCOBOL               Compiler/executor        → syntax + runtime
  extract_cfg_summary.py Normalises REKT output   → validation/structure/

Layer 3 — Ground Truth Oracle (derived from Layer 2, committed)
Layer 4 — LLM Claims (untrusted input)
Layer 5 — Gate (Layer 3 vs Layer 4)
```

**The lint step runs FIRST in Layer 2 — before REKT and before GnuCOBOL.**
If any ERROR-severity lint fires, the source must be fixed before continuing
down the pipeline. WARNING and INFO findings are advisory.

## Why Lints — Not Fine-Tunes

The original question from the partners was whether source-level incompatibilities
should be handled by fine-tuning the LLM on a corrected corpus.

**The answer is: lints, not fine-tunes.**

| Dimension | Lint | Fine-Tune |
|---|---|---|
| Runs on original source | ✅ Yes | ❌ Needs labelled pairs |
| Deterministic / auditable | ✅ Yes — line numbers, rule IDs | ❌ Black box |
| Cost | ✅ Free — Python, no GPU | ❌ Expensive |
| Grows with observed failures | ✅ Add a rule | ❌ Retrain |
| Survives project handoff | ✅ Rules are version-controlled | ❌ Model not in repo |
| Catches bugs not yet seen | ❌ Pattern-based | ✅ Generalises |
| Modifies source truth | ❌ No — findings only | ✅ Risk of hallucinated changes |

Lints handle the **known, deterministic failure modes** we have already observed.
Fine-tuning remains relevant only for the Layer 4→5 problem: improving the LLM's
*output quality* on translation tasks — not for cleaning the input source.

## Usage

```powershell
# Lint all 31 programs
py -3 validation/lint_cobol/lint_cobol.py

# Lint one program only
py -3 validation/lint_cobol/lint_cobol.py --only COCRDLIC

# Fail the pipeline if any ERROR exists (for CI)
py -3 validation/lint_cobol/lint_cobol.py --fail-on-error
```

## Output

`lint_results/lint_results.json`
```json
{
  "generated_at": "2026-05-02T...",
  "layer": 2,
  "summary": { "total_files": 31, "total_errors": 0, "total_warnings": 4, "total_info": 87 },
  "files": { "COCRDLIC": { "status": "PASS", "errors": 0, "warnings": 0, "info": 12 } },
  "findings": [ ... ]
}
```

## Pipeline Integration

Add to `run_rekt_all.py` before the smojol-cli call:

```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, "validation/lint_cobol/lint_cobol.py", "--fail-on-error"],
    check=False
)
if result.returncode != 0:
    print("[pipeline] Lint errors detected — fix source before REKT analysis")
    sys.exit(1)
```

## Adding New Rules

See `rules/README.md` for the full catalogue, classification system, and
step-by-step instructions for adding a new rule.
