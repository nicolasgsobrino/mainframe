---
schema_version: "cobol-md/1.0"
document: "COBOL-MD-PIPELINE"
version: "1.1.0"
status: "ACTIVE"
authored: "2026-04-23"
author: "Mark Snow"
aifirst_protocol: "aifirst/1.0"
changelog:
  - version: "1.0.0"
    date: "2026-04-23"
    notes: "Initial pipeline — 5 phases, T01–T05, knowledge graph node model"
  - version: "1.1.0"
    date: "2026-04-23"
    notes: "Gemini integration: Phase 0 CFG pre-processing, T02-R REDEFINES subcheck, dead code labeling, trajectory synthesis in Phase 4"
---

# COBOL→English Middle Layer Pipeline

## Mission

Prove that every semantic element in a COBOL program can be losslessly expressed in structured English inside a YAML-headered MD file. This creates an **English middle layer** — a human-readable, machine-parseable, knowledge-graph-ready representation that replaces COBOL as the source of truth for business logic.

This is **not** a code documentation tool. The MD file is an independent semantic artifact. Raw COBOL source stays in `app/cbl/` and is never embedded in the output.

---

## Pipeline Overview

```
[COBOL Source]
      │
      ▼
 Phase 0: CFG Pre-Processing  ← NEW (Gemini v1.1.0)
      │  Tool: Cobol-REKT
      │  Output: validation/structure/<ID>_cfg.json
      │  Dead code labeled; GOTO map resolved
      │
      ▼
 Phase 1: Baseline Translation (pre-fine-tune)
      │  Model: Qwen3.635B A3B
      │  Input: COBOL source + CFG artifact
      │  Output: translations/baseline/*.md
      │
      ▼
 Phase 2: Gated Validation (T01–T05 + T02-R)  ← T02-R NEW (Gemini v1.1.0)
      │  Protocol: /aifirst G3
      │  Halt-on-fail per tier
      │
      ▼
 Phase 3: Gold Set Construction
      │  Human review + correction
      │  Output: translations/gold/*.md
      │  Size: 6–8 verified pairs
      │
      ▼
 Phase 4: QLoRA Fine-Tuning  ← Trajectory synthesis added (Gemini v1.1.0)
      │  Hardware: HP Z8 Fury G5 / Zbook (ROCm, AMD)
      │  Input: gold/*.md pairs + trajectory pairs from BLOCKED run.log events
      │
      ▼
 Phase 5: Post-Fine-Tune Validation + SWE-bench
      │  Same T01–T05+T02-R suite, same files
      │  SWE-bench Lite delta = proof document
      │
      ▼
[English Middle Layer — Knowledge Graph Ready]
```

---

## Phase 0 — CFG Pre-Processing *(Gemini v1.1.0)*

**Tool:** [Cobol-REKT](https://github.com/avishek-sen-gupta/cobol-rekt) (tested specifically on CardDemo)
**Input:** Raw `.cbl` files from `app/cbl/`
**Output:** `validation/structure/<PROGRAM_ID>_cfg.json`
**Runs before:** Phase 1 translation — Phase 1 cannot start without CFG artifacts

### Why This Phase Exists

GOTO-driven spaghetti code is a first-class LLM failure mode in COBOL translation. CardDemo's larger programs (especially `COACTUPC.cbl` at 182KB) contain heavy PERFORM/GOTO structures that cause LLMs to hallucinate recursive calls or infinite loops when fed raw source. Phase 0 resolves this before any model ever sees the code.

### Steps

1. **CFG extraction** — Run Cobol-REKT to produce a Control Flow Graph for every pilot corpus file. Reducible GOTO loops are resolved into structured `WHILE`/`IF` constructs in the CFG representation
2. **Reachability analysis** — Cobol-REKT static analysis marks every paragraph and data item as `reachable: true/false`. Unreachable items = dead code (typically 20–30% of legacy codebases per Gemini research)
3. **GOTO map** — All GOTO jumps are recorded as directed edges with source/target paragraph names. Any irreducible GOTO (not resolvable to a structured construct) is flagged with `goto_flag: true` for human review before Phase 1
4. **REDEFINES inventory** — All REDEFINES clauses are extracted and catalogued in the CFG JSON for T02-R validation

### CFG JSON Structure

```json
{
  "program_id": "CBCUS01C",
  "source_sha": "88a99d7f...",
  "paragraphs": [
    {
      "name": "0100-INIT",
      "reachable": true,
      "performs": ["0200-READ-CUST"],
      "goto_targets": [],
      "goto_flag": false
    }
  ],
  "data_items": [
    {
      "name": "WS-CUSTOMER-ID",
      "reachable": true,
      "redefines": null
    }
  ],
  "redefines_clauses": [],
  "dead_code_paragraphs": [],
  "dead_code_items": [],
  "irreducible_gotos": []
}
```

### Prompt Contract for Phase 1 (updated)

Every Phase 1 translation prompt MUST include:
- Full COBOL source
- The CFG JSON artifact for this file
- `docs/COBOL-MD-SCHEMA.md` v1.0.2 as schema contract
- `business_domain` and `subtype` pre-assigned values
- Instruction to use `reachable` values from CFG for all `procedure_paragraphs[]` and `data_items[]` entries
- Instruction to expand all `redefines_clauses` from CFG into full `redefines_interpretations[]` entries
- Explicit prohibition on embedding raw COBOL in output

---

## Phase 1 — Baseline Translation

**Model:** Qwen3.635B A3B (via Lemonade Server / Ollama on Z8)
**Input:** COBOL source + Phase 0 CFG artifact
**Output:** `translations/baseline/<PROGRAM_ID>.md`
**Schema:** `docs/COBOL-MD-SCHEMA.md` v1.0.2

### Pilot Corpus Run Order

| # | File | `business_domain` | `subtype` | Size | GOTO Risk |
|---|------|------------------|-----------|------|----------|
| 1 | COBSWAIT.cbl | Utility | Utility | 2KB | Low |
| 2 | CBCUS01C.cbl | Customer Management | Batch | 7KB | Low |
| 3 | COSGN00C.cbl | Administration | CICS-Online | 10KB | Medium |
| 4 | COMEN01C.cbl | Administration | Menu | 12KB | Low |
| 5 | CBACT01C.cbl | Account Management | Batch | 17KB | Medium |
| 6 | CBTRN01C.cbl | Transaction Processing | Batch | 18KB | Medium |
| 7 | CBTRN02C.cbl | Transaction Processing | Batch | 59KB | High — post-FT |
| 8 | COACTUPC.cbl | Account Management | CICS-Online | 182KB | High — post-FT |

GOTO Risk column derived from Phase 0 `irreducible_gotos` count in CFG JSON.

---

## Phase 2 — Gated Validation

All validation runs under `/aifirst` protocol (see `Morty:.claude/protocol/AIFIRST-SPEC.md`).

### Tier Definitions for COBOL→MD

| Tier | Test | Tool | Threshold |
|------|------|------|-----------|
| T01 | YAML parses; all required fields present; `business_domain` and `subtype` valid enums; `cfg_source` path exists | `pyyaml` + JSON Schema | 100% |
| T02 | Every COBOL SECTION, PARAGRAPH, and 01-level DATA item in MD; `procedure_paragraphs[]` matches CFG paragraph list | GnuCOBOL parse + CFG diff | 100% |
| T02-R | Every `redefines != null` item has `redefines_interpretations[]` with ≥2 entries, all subfields populated | `validate_t02r.py` | 100% |
| T03 | All `data_items[]` field-match COBOL DATA DIVISION; CFG `reachable` values match MD `dead_code_flag` values | Field-level comparator + CFG cross-check | ≥95% |
| T04 | Business logic semantically faithful; no rule in COBOL absent from MD; dead-code rules marked `reachable: false` | LLM-as-judge rubric (0–5 per paragraph) | ≥85% |
| T05 | Model hasn't degraded on general code tasks | SWE-bench Lite before/after | ≥ baseline |

### T02-R Detail

For every item in `data_items[]` where `redefines != null`:
1. `redefines_interpretations[]` must be present and have ≥2 entries
2. Each entry requires: `condition`, `interpreted_as`, `encoding`
3. `condition` must reference a field that exists in `data_items[]`
4. T02-R is absolute — no threshold, no partial credit

This check exists because REDEFINES misinterpretation is a documented production failure mode: a single memory address treated as different data types at runtime. A translation that passes T02 but fails T02-R looks complete but contains corrupted business logic.

### T04 Rubric (unchanged)

- **5** — Complete, accurate, no information lost
- **4** — Minor phrasing imprecision, all information present  
- **3** — Some implicit logic missing, main flow captured
- **2** — Significant business rule absent or wrong
- **1** — Paragraph present but semantically incorrect
- **0** — Paragraph missing or gibberish

Dead code paragraphs (`reachable: false`) are scored but weighted at 0.1× in the T04 mean — they must be present but semantic accuracy is lower priority.

---

## Phase 3 — Gold Set Construction

For each baseline translation that reaches G3:
- Human review against original COBOL source
- Verify `redefines_interpretations[]` against subject matter expert knowledge (this is the hardest review step)
- Correct T04 deficiencies
- Verify dead code labels from Phase 0 CFG are correct
- Save corrected file to `translations/gold/<PROGRAM_ID>.md`

Gold set: minimum 6 files (Tiers S and M). Gold files are the primary fine-tuning training pairs.

---

## Phase 4 — QLoRA Fine-Tuning

**Hardware:** HP Z8 Fury G5 + RTX 6000 Ada (ROCm/AMD — not CUDA)
**Base model:** Qwen3.635B A3B
**Method:** QLoRA (4-bit NF4 quantization)

### Recommended Config

```yaml
method: qlora
quantization: nf4
rank_r: 16
alpha: 32
learning_rate: 2.0e-4
epochs: 3
batch_size: 4
gradient_checkpointing: true
warmup_steps: 50
target_modules: [q_proj, v_proj, k_proj, o_proj]
```

### Training Signal: Three Input Streams *(Gemini trajectory synthesis v1.1.0)*

#### Stream 1 — Primary Supervised Pairs
`(COBOL source + CFG JSON) → gold/*.md` — the baseline supervised signal.

#### Stream 2 — Positive Run Log Events
From `/aifirst` `run.log`: every `"status": "PASS"` event at T03/T04 contributes a positive example.

#### Stream 3 — Trajectory Pairs (new in v1.1.0)

When a T04 paragraph score < 3, capture a **4-tuple correction trajectory**:

```
[
  COBOL paragraph source,          ← input
  incorrect translation,            ← model's failure output  
  T04 judge feedback,               ← "Missing: REDEFINES condition for WS-TRANS-TYPE"
  corrected translation             ← gold correction
]
```

This 4-tuple trains the model to **reason through errors**, not just pattern-match correct outputs. It is more effective than training on correct examples alone because it explicitly teaches error recognition and self-correction. The raw material is already in `/aifirst` `run.log` BLOCKED events — the enhancement is capturing the (failure → feedback → correction) chain.

Trajectory pairs are particularly valuable for REDEFINES clauses and GOTO-heavy paragraphs — the two highest-failure-rate constructs in baseline runs.

---

## Phase 5 — Post-Fine-Tune Validation

Re-run identical T01–T05+T02-R suite on the same 8 pilot files using the fine-tuned model.

### Proof Document Metrics

| Metric | Pre-FT | Post-FT | Delta | Pass? |
|--------|--------|---------|-------|-------|
| T01 schema validity | — | — | — | 100% required |
| T02 structural completeness | — | — | — | 100% required |
| T02-R REDEFINES completeness | — | — | — | 100% required |
| T03 functional score (mean) | — | — | — | ≥0.95 required |
| T04 semantic score (mean) | — | — | — | ≥0.85 required |
| SWE-bench Lite | — | — | — | ≥ baseline |

Populated after each run. Delta = proof of fine-tuning value. SWE-bench delta = proof of no regression.

---

## Directory Structure

```
aws-mainframe-modernization-carddemo/
  app/cbl/                         ← original COBOL source (untouched)
  docs/
    COBOL-MD-SCHEMA.md             ← schema spec v1.0.2
    COBOL-MD-PIPELINE.md           ← this file v1.1.0
  translations/
    baseline/                      ← Phase 1 output
    gold/                          ← Phase 3 human-verified training pairs
    post-finetune/                 ← Phase 5 output
  validation/
    structure/                     ← Phase 0 CFG + structure JSON per file
    reports/                       ← T01–T05+T02-R results per run (JSON-L)
  scripts/
    extract_structure.py           ← GnuCOBOL → structure JSON
    validate_t01.py                ← YAML schema validator
    validate_t02.py                ← structural completeness diff
    validate_t02r.py               ← REDEFINES interpretations subcheck (new)
    validate_t03.py                ← field-level data item comparator
    score_t04.py                   ← LLM-as-judge rubric runner
    build_trajectories.py          ← extracts trajectory pairs from run.log (new)
    run_sweBench.sh                ← SWE-bench Lite wrapper
  .aifirst/
    runs/                          ← /aifirst run logs (JSON-L)
```

---

## Toward the Knowledge Graph

| Schema Field | Graph Element |
|-------------|---------------|
| `program_id` | Node identity |
| `business_domain` | Cluster / community label (Louvain) |
| `subtype` | Subgraph partition (CICS-Online / Batch) |
| `calls_to[]` | Directed edge: Program→Program |
| `called_by[]` | Reverse index edge |
| `copybooks_used[]` | Edge: Program→Copybook |
| `file_control[]` | Edge: Program→VsamFile |
| `business_rules[]` | Property node: BusinessRule `{reachable}` |
| `data_items[]` | Property node: DataItem `{dead_code_flag}` |
| `procedure_paragraphs[]` | Property node: Paragraph `{reachable, goto_targets}` |

Dead code nodes are retained in the graph with a `reachable: false` property. Default queries filter them out; forensic/compliance queries can include them explicitly.

---

## Related Documents

- Schema spec: `docs/COBOL-MD-SCHEMA.md` v1.0.2
- AiFirst protocol: [Morty/.claude/protocol/AIFIRST-SPEC.md](https://github.com/MrSnowNB/Morty/blob/main/.claude/protocol/AIFIRST-SPEC.md)
- AiFirst slash command: [Morty/.claude/commands/aifirst.md](https://github.com/MrSnowNB/Morty/blob/main/.claude/commands/aifirst.md)
- Cobol-REKT (CFG tool): https://github.com/avishek-sen-gupta/cobol-rekt

---

## Version History

| Version | Date | Author | Notes |
|---------|------|--------|-------|
| 1.0.0 | 2026-04-23 | Mark Snow | Initial pipeline — 5 phases, T01–T05 |
| 1.1.0 | 2026-04-23 | Mark Snow | Gemini: Phase 0 CFG pre-processing, T02-R REDEFINES subcheck, dead code labeling, trajectory synthesis in Phase 4, `build_trajectories.py` script, updated directory structure |
