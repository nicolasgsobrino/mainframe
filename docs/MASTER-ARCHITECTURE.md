---
schema_version: "cobol-md/1.0"
document: "MASTER-ARCHITECTURE"
version: "1.0.0"
status: "ACTIVE"
authored: "2026-04-23"
author: "Mark Snow"
aifirst_protocol: "aifirst/1.0"
purpose: "Autonomous implementation handoff document. Pass this file + its referenced specs to any capable model to attempt a full baseline implementation of the COBOL-to-English middle-layer pipeline."
---

# AI-First Master Architecture
## COBOL → English Middle Layer Pipeline
### Autonomous Implementation Specification

> **Repo:** [MrSnowNB/aws-mainframe-modernization-carddemo](https://github.com/MrSnowNB/aws-mainframe-modernization-carddemo)
> **Branch:** `feat/cobol-md-schema-v1`
> **Protocol:** `/aifirst` v1.0 (see [Morty repo](https://github.com/MrSnowNB/Morty))
> **Spec Version:** 1.0.0 — 2026-04-23
> **Handoff Intent:** Pass this document to an autonomous model/agent to attempt a complete baseline implementation. Gaps and failure modes surfaced during autonomous execution become the human review agenda.

---

## 1. Mission Statement

This project proves that every semantic element in a COBOL program can be **losslessly expressed in structured English** inside a YAML-headered Markdown file. The output is an **English middle layer** — a human-readable, machine-parseable, knowledge-graph-ready artifact that replaces COBOL as the source of truth for business logic.

This is **not** code documentation. The Markdown file is an independent semantic artifact. Raw COBOL source remains in `app/cbl/` and is **never** embedded in the translated output.

### Success Condition

The project is proven when:
1. A stratified pilot corpus of 6 COBOL files passes all validation tiers (T01–T05 + T02-R)
2. A fine-tuned model scores higher than baseline on T03 and T04 on the same corpus
3. SWE-bench Lite score is unchanged or improved after fine-tuning (no regression)
4. All results are logged in `/aifirst` `run.log` JSON-L format and traceable to a `task_id`

---

## 2. Reference Documents

All reference documents live in `docs/` on branch `feat/cobol-md-schema-v1`:

| Document | Path | Purpose |
|----------|------|---------|
| This file | `docs/MASTER-ARCHITECTURE.md` | Authoritative implementation spec |
| Schema spec | `docs/COBOL-MD-SCHEMA.md` v1.0.2 | YAML front-matter contract for all translated files |
| Pipeline spec | `docs/COBOL-MD-PIPELINE.md` v1.1.0 | 6-phase execution pipeline with validation tiers |
| AiFirst spec | `Morty:.claude/protocol/AIFIRST-SPEC.md` | Gate protocol (G0–G4), run.log schema |
| AiFirst command | `Morty:.claude/commands/aifirst.md` | `/aifirst` slash command definition |

**If any document is inaccessible, STOP and report the missing document. Do not proceed with assumptions.**

---

## 3. Pilot Corpus

The implementation operates on a stratified subset of COBOL files from `app/cbl/`. Do not translate the full repository. The pilot corpus is:

| Priority | File | Size | `business_domain` | `subtype` | Complexity |
|----------|------|------|------------------|-----------|------------|
| 1 (smoke) | `COBSWAIT.cbl` | 2KB | Utility | Utility | S |
| 2 | `CBCUS01C.cbl` | 7KB | Customer Management | Batch | S |
| 3 | `COSGN00C.cbl` | 10KB | Administration | CICS-Online | M |
| 4 | `COMEN01C.cbl` | 12KB | Administration | Menu | M |
| 5 | `CBACT01C.cbl` | 17KB | Account Management | Batch | M |
| 6 | `CBTRN01C.cbl` | 18KB | Transaction Processing | Batch | L |
| HOLD | `CBTRN02C.cbl` | 59KB | Transaction Processing | Batch | L |
| HOLD | `COACTUPC.cbl` | 182KB | Account Management | CICS-Online | XL |

Files marked HOLD are used only for post-fine-tune generalization testing. Do not include them in the baseline run.

**Process files in priority order 1→6. Gate each file through T01–T05+T02-R before moving to the next. A failure on any file halts that file; continue to the next file unless the failure is systemic.**

---

## 4. Full Pipeline (6 Phases)

### Phase 0 — CFG Pre-Processing

**Tool:** [Cobol-REKT](https://github.com/avishek-sen-gupta/cobol-rekt)
**Input:** `app/cbl/<PROGRAM_ID>.cbl`
**Output:** `validation/structure/<PROGRAM_ID>_cfg.json`
**Blocking:** Phase 1 cannot start for a file until its CFG artifact exists.

**Steps:**
1. Run Cobol-REKT on the source file to produce a Control Flow Graph
2. Extract all paragraph names with `reachable: true/false` (static reachability)
3. Record all GOTO targets; flag irreducible GOTOs as `goto_flag: true`
4. Inventory all REDEFINES clauses
5. Write output to `validation/structure/<PROGRAM_ID>_cfg.json` using the CFG JSON structure defined in `COBOL-MD-PIPELINE.md §Phase 0`

**Failure modes to watch:**
- Cobol-REKT parse failure on non-standard COBOL dialects — log and skip file if unrecoverable
- Irreducible GOTO loops that cannot be resolved — flag `goto_flag: true`, surface to human before Phase 1
- Programs with zero reachable paragraphs (full dead code) — flag and skip

---

### Phase 1 — Baseline Translation

**Model:** Qwen3.635B A3B (or best available; log exact model identifier in `translating_agent`)
**Input:** COBOL source + CFG JSON artifact
**Output:** `translations/baseline/<PROGRAM_ID>.md`
**Schema contract:** `docs/COBOL-MD-SCHEMA.md` v1.0.2

**Prompt contract (mandatory):**

```
You are translating a COBOL program into a structured English Markdown file.
Schema contract: [full contents of docs/COBOL-MD-SCHEMA.md]
CFG artifact: [full contents of validation/structure/<PROGRAM_ID>_cfg.json]
Source file: [full contents of app/cbl/<PROGRAM_ID>.cbl]
business_domain: [value from pilot corpus table]
subtype: [value from pilot corpus table]

Rules:
1. Populate ALL YAML front-matter fields. No field may be null unless the schema marks it optional.
2. Use reachable values from the CFG artifact for all procedure_paragraphs[] and data_items[] entries.
3. Expand every REDEFINES clause from the CFG into a full redefines_interpretations[] entry with condition, interpreted_as, and encoding.
4. Do NOT embed raw COBOL source in the output.
5. Do NOT omit any paragraph, section, or data item present in the source.
6. The validation block must be left as all null / PENDING — it is populated by the validation step, not by you.
7. Populate aifirst_task_id with the current task ID.
8. cfg_source must point to: validation/structure/<PROGRAM_ID>_cfg.json
```

**Failure modes to watch:**
- Context window overflow on files >15KB — chunk the source into DIVISION sections if needed, merge outputs
- Model omitting REDEFINES entries (most common failure) — T02-R will catch this
- Model embedding raw COBOL in fenced code blocks — post-process to strip if present
- Missing `business_rules[]` entries on complex conditional logic — T04 will catch this
- Hallucinated `calls_to[]` entries for programs that don’t exist in the repo — cross-validate against repo file list

---

### Phase 2 — Gated Validation

**Protocol:** `/aifirst` G3 gate
**All tiers are run sequentially. A FAIL at any tier halts that tier and writes BLOCKED to run.log. Do not skip tiers.**

#### T01 — Schema Validity (threshold: 100%)

Script: `scripts/validate_t01.py`

Checks:
- YAML front-matter parses without error
- All required fields present (per schema v1.0.2 field reference)
- `business_domain` is one of the 8 valid enum values
- `subtype` is one of the 5 valid enum values
- `cfg_source` path exists in the repo
- `status` in `validation` block is `PENDING`
- `aifirst_task_id` matches current task ID format `T-YYYY-MM-DD-NNN`

Script stub:
```python
import yaml, json, sys
from pathlib import Path

REQUIRED_FIELDS = [
    "schema_version", "program_id", "source_file", "source_sha",
    "translation_date", "translating_agent", "aifirst_task_id", "cfg_source",
    "business_domain", "subtype", "calls_to", "called_by", "copybooks_used",
    "file_control", "data_items", "procedure_paragraphs", "business_rules", "validation"
]
BUSINESS_DOMAINS = [
    "Account Management", "Transaction Processing", "Customer Management",
    "Authorization", "Reporting", "Administration", "Utility", "Menu"
]
SUBTYPES = ["CICS-Online", "Batch", "Utility", "Menu", "Copybook"]

def validate_t01(md_path: str) -> dict:
    content = Path(md_path).read_text()
    # Extract YAML front-matter between --- delimiters
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {"pass": False, "error": "No YAML front-matter found"}
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return {"pass": False, "error": str(e)}
    errors = []
    for f in REQUIRED_FIELDS:
        if f not in data:
            errors.append(f"Missing required field: {f}")
    if data.get("business_domain") not in BUSINESS_DOMAINS:
        errors.append(f"Invalid business_domain: {data.get('business_domain')}")
    if data.get("subtype") not in SUBTYPES:
        errors.append(f"Invalid subtype: {data.get('subtype')}")
    cfg_path = Path(data.get("cfg_source", ""))
    if not cfg_path.exists():
        errors.append(f"cfg_source path does not exist: {cfg_path}")
    if data.get("validation", {}).get("overall") != "PENDING":
        errors.append("validation.overall must be PENDING at translation time")
    return {"pass": len(errors) == 0, "errors": errors}
```

#### T02 — Structural Completeness (threshold: 100%)

Script: `scripts/validate_t02.py`

Checks:
1. Run `cobc -fsyntax-only` on source to extract paragraph/section/data item list
2. Parse `procedure_paragraphs[]` from translated MD
3. Diff: every paragraph in source must appear in MD
4. Every 01-level DATA DIVISION item must appear in `data_items[]`
5. Every COPY statement reference must appear in `copybooks_used[]`

Absolute — no threshold. Missing element = FAIL.

#### T02-R — REDEFINES Completeness (threshold: 100%)

Script: `scripts/validate_t02r.py`

For every item in `data_items[]` where `redefines != null`:
1. `redefines_interpretations[]` must be present
2. Must contain ≥2 entries
3. Each entry must have `condition`, `interpreted_as`, `encoding`
4. `condition` value must reference a field in `data_items[]`

Absolute — no threshold.

**Why this matters:** REDEFINES misinterpretation is a documented production failure mode. A single memory address treated as two different data types at runtime. A translation that passes T02 but fails T02-R looks complete but is semantically corrupted.

#### T03 — Functional Score (threshold: ≥95%)

Script: `scripts/validate_t03.py`

For every item in `data_items[]`:
- `name` matches COBOL DATA DIVISION exactly (no case normalization)
- `level` matches
- `picture` matches
- `usage` matches or is null when DISPLAY
- `reachable` / `dead_code_flag` matches CFG JSON value

Score = matched items / total items. Threshold ≥0.95.

#### T04 — Semantic Accuracy (threshold: ≥85%)

Script: `scripts/score_t04.py`

For each paragraph in `procedure_paragraphs[]`:
- Run LLM-as-judge with the following prompt:

```
You are evaluating the semantic accuracy of a COBOL-to-English translation.

COBOL paragraph source:
[raw COBOL paragraph text]

English translation:
[corresponding paragraph summary from procedure_paragraphs[].summary]

Score from 0 to 5:
5 = Complete, accurate, no information lost
4 = Minor phrasing imprecision, all information present
3 = Some implicit logic missing, main flow captured
2 = Significant business rule absent or wrong
1 = Paragraph present but semantically incorrect
0 = Paragraph missing or gibberish

Return JSON: {"paragraph": "<name>", "score": <int>, "reason": "<one sentence>"}
```

Dead code paragraphs (`reachable: false`) are scored but weighted at 0.1× in the mean.
Overall T04 = weighted mean across all paragraphs. Threshold ≥0.85.

Capture all T04 scores with paragraph name, score, and reason. These are training signal for Phase 4. Paragraphs scoring <3 generate trajectory pairs.

#### T05 — SWE-bench Regression (threshold: ≥ baseline)

Script: `scripts/run_sweBench.sh`

Run SWE-bench Lite on the same model used for translation. Record score. This is the pre-fine-tune baseline. Post-fine-tune must meet or exceed this score.

If SWE-bench environment is unavailable, record `t05_regression_pass: null` and flag as `DEFERRED` in run.log. Do not block on T05 if the environment cannot be set up — it is the only tier allowed to defer.

---

### Phase 3 — Gold Set Construction

**This phase requires human review. An autonomous agent produces candidate gold files; a human must verify and sign off.**

For each baseline translation that passed G3:
1. Human expert reviews translation against original COBOL source
2. Special attention to `redefines_interpretations[]` — this is the highest human-expertise requirement
3. Correct any T04 deficiencies found during review
4. Verify dead code labels from Phase 0 are accurate
5. Save verified file to `translations/gold/<PROGRAM_ID>.md`

Minimum gold set: 6 files (priority 1–6 from pilot corpus).

**Autonomous agent role in Phase 3:** Produce the candidate files and a Phase 3 review checklist per file. Do not mark any file as gold without human sign-off.

---

### Phase 4 — QLoRA Fine-Tuning

**Hardware target:** HP Z8 Fury G5 + RTX 6000 Ada (ROCm/AMD — not CUDA)
**Base model:** Qwen3.635B A3B
**Method:** QLoRA 4-bit NF4

#### Config

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

#### Training Data: Three Streams

**Stream 1 — Primary supervised pairs**
Format: `(COBOL source + CFG JSON) → gold/*.md`
One pair per file in gold set.

**Stream 2 — Positive run.log events**
Extract all `"status": "PASS"` tier events at T03/T04 from run.log.
Each is a positive reinforcement signal for the corresponding (input → output) pair.

**Stream 3 — Trajectory pairs** *(Gemini-derived)*

Script: `scripts/build_trajectories.py`

For every T04 paragraph score < 3:
Capture 4-tuple:
```
[
  cobol_paragraph_source,      # input
  incorrect_translation,       # model's failure output
  t04_judge_feedback,          # judge's reason string
  corrected_translation        # from gold file
]
```
This trains error-correction reasoning, not just pattern-matching. Do not generate synthetic trajectory pairs — only real BLOCKED run.log events qualify.

**Stream data must not include synthetic or mocked content. All training data must derive from real run artifacts.**

---

### Phase 5 — Post-Fine-Tune Validation

Re-run the full T01–T05+T02-R suite on the same 6 pilot files using the fine-tuned model.

Then re-run on the 2 HOLD files (`CBTRN02C.cbl`, `COACTUPC.cbl`) to test generalization.

Record results in the proof document table:

| Metric | Pre-FT | Post-FT | Delta | Pass? |
|--------|--------|---------|-------|-------|
| T01 schema validity | — | — | — | 100% required |
| T02 structural completeness | — | — | — | 100% required |
| T02-R REDEFINES completeness | — | — | — | 100% required |
| T03 functional score (mean) | — | — | — | ≥0.95 required |
| T04 semantic score (mean) | — | — | — | ≥0.85 required |
| SWE-bench Lite | — | — | — | ≥ baseline |
| T03 — HOLD files | — | — | — | ≥0.90 (generalization) |
| T04 — HOLD files | — | — | — | ≥0.80 (generalization) |

---

## 5. Repository Structure

All files created by this pipeline must land in these paths. Do not create files outside this structure.

```
aws-mainframe-modernization-carddemo/
├── app/cbl/                          ← COBOL source (READ ONLY — never modify)
├── docs/
│   ├── MASTER-ARCHITECTURE.md         ← this file
│   ├── COBOL-MD-SCHEMA.md             ← schema spec v1.0.2
│   └── COBOL-MD-PIPELINE.md           ← pipeline spec v1.1.0
├── translations/
│   ├── baseline/                      ← Phase 1 output (one .md per program)
│   ├── gold/                          ← Phase 3 human-verified training pairs
│   └── post-finetune/                 ← Phase 5 output
├── validation/
│   ├── structure/                     ← Phase 0: CFG JSON per file
│   └── reports/                       ← T01–T05 results per run (JSON-L)
├── scripts/
│   ├── validate_t01.py                ← YAML schema validator (stub above)
│   ├── validate_t02.py                ← GnuCOBOL parse diff
│   ├── validate_t02r.py               ← REDEFINES interpretations check
│   ├── validate_t03.py                ← field-level data item comparator
│   ├── score_t04.py                   ← LLM-as-judge rubric runner
│   ├── build_trajectories.py          ← trajectory pair extractor from run.log
│   └── run_sweBench.sh                ← SWE-bench Lite wrapper
├── training/
│   ├── stream1_supervised/            ← (input, gold) pairs
│   ├── stream2_positive/              ← positive run.log events
│   └── stream3_trajectories/          ← 4-tuple correction trajectories
└── .aifirst/
    └── runs/                          ← /aifirst run logs (JSON-L)
        └── <task_id>/
            ├── G0-plan.md
            ├── G1-scaffold.md
            ├── G2-execute.md
            ├── G3-validate.md
            ├── G4-commit.md
            └── run.log
```

---

## 6. run.log Event Schema

All pipeline events must be logged to `.aifirst/runs/<task_id>/run.log` as append-only JSON-L.

```jsonc
// Phase 0 complete
{"event":"phase_complete","phase":0,"file":"COBSWAIT.cbl","task_id":"T-YYYY-MM-DD-NNN","gotos_resolved":true,"dead_code_count":0,"redefines_count":0,"ts":"ISO-8601"}

// Translation complete
{"event":"step","phase":1,"step_id":"T-...-S-001","file":"COBSWAIT.cbl","status":"PASS","tokens_used":4821,"ts":"ISO-8601"}

// Tier result
{"event":"tier","tier":"T04","file":"COBSWAIT.cbl","score":0.93,"threshold":0.85,"status":"PASS","ts":"ISO-8601"}

// Tier blocked
{"event":"blocked","tier":"T04","file":"CBCUS01C.cbl","score":0.79,"threshold":0.85,"reason":"Paragraph 1200-DELETE-VALIDATE missing guard rule for inactive status","ts":"ISO-8601"}

// Trajectory pair captured
{"event":"trajectory_captured","file":"CBCUS01C.cbl","paragraph":"1200-DELETE-VALIDATE","t04_score":2,"reason":"Missing guard rule","ts":"ISO-8601"}

// Phase complete
{"event":"phase_complete","phase":2,"files_passed":5,"files_blocked":1,"ts":"ISO-8601"}
```

---

## 7. Hard Rules

These rules are non-negotiable. Violation of any hard rule is an automatic G3 FAIL.

1. **No synthetic data** — All training data, validation inputs, and run.log events must derive from real pipeline execution. No mocked, simulated, or generated data at any tier.
2. **No raw COBOL in MD output** — The translated `.md` file must not contain COBOL source in any form. It is a pure English artifact.
3. **No self-certification** — The translating agent must not populate the `validation` block. Only the validation scripts populate it.
4. **Append-only run.log** — Never overwrite or truncate. If a log event needs correction, append a `"event":"correction"` entry.
5. **app/cbl/ is read-only** — Never modify, rename, or delete any file in `app/cbl/`. Source integrity is the ground truth of the entire pipeline.
6. **Gate order is strict** — Phases execute in order 0→1→2→3→4→5. No phase may begin before the previous phase's outputs exist. Phase 3 requires human sign-off before Phase 4 begins.
7. **task_id required** — Every run must be initiated with a valid `/aifirst` task_id in format `T-YYYY-MM-DD-NNN`. No anonymous runs.

---

## 8. Known Failure Modes & Mitigations

This section documents the anticipated failure modes at each phase. Autonomous agents should treat this as a pre-flight checklist and capture any novel failure modes in a new `failure_modes.log` entry.

| Phase | Failure Mode | Probability | Impact | Mitigation |
|-------|-------------|-------------|--------|------------|
| 0 | Cobol-REKT parse failure on non-standard dialect | Medium | Blocks file | Log and skip; flag for human review |
| 0 | Irreducible GOTO loops in CICS programs | High for COACTUPC | Corrupts CFG | Flag `goto_flag: true`; surface to human before Phase 1 |
| 1 | Context window overflow on files >15KB | High | Incomplete translation | Chunk by DIVISION; merge outputs |
| 1 | Model omits REDEFINES entries | High | T02-R FAIL | T02-R catches; include explicit REDEFINES instruction in prompt |
| 1 | Model embeds raw COBOL in output | Medium | Schema violation | Post-process strip; T01 catches |
| 1 | Hallucinated `calls_to[]` entries | Medium | Graph corruption | Cross-validate against `app/cbl/` file list |
| 1 | Missing `business_rules[]` on complex conditional logic | High | T04 score drop | CFG GOTO map provides conditional branch inventory as prompt context |
| 2 | T04 LLM-as-judge hallucination in scoring | Medium | False PASS | Use temperature=0; require JSON output; validate score is 0–5 |
| 2 | GnuCOBOL unavailable in environment | Medium | T02 blocked | Fall back to regex paragraph extractor; flag as approximate |
| 3 | Human reviewer unavailable | — | Phase 4 blocked | Queue candidate gold files; document review backlog |
| 4 | ROCm/AMD incompatibility with QLoRA library | Medium | Phase 4 blocked | Test `bitsandbytes` ROCm fork first; fallback to CPU with reduced batch |
| 4 | Insufficient VRAM for fine-tuning | Low (RTX 6000 Ada has 48GB) | Phase 4 slow | Reduce batch_size to 1; enable gradient checkpointing |
| 4 | Trajectory pairs too few (<10) | Medium | Weak fine-tune signal | Supplement with copybook translations to increase corpus |
| 5 | Fine-tuned model T04 regression (worse than baseline) | Medium | Pipeline failure | Reduce epochs to 2; increase LoRA alpha; re-run |
| 5 | SWE-bench environment unavailable | Medium | T05 deferred | Record `DEFERRED`; proceed; flag in proof document |

---

## 9. Autonomous Agent Execution Instructions

If you are an autonomous agent reading this document, follow these instructions exactly:

### Pre-Flight Checklist

Before executing any phase:
- [ ] Read `docs/COBOL-MD-SCHEMA.md` v1.0.2 in full
- [ ] Read `docs/COBOL-MD-PIPELINE.md` v1.1.0 in full
- [ ] Verify `app/cbl/` contains the 6 pilot corpus files
- [ ] Verify Cobol-REKT is available in the environment
- [ ] Verify GnuCOBOL (`cobc`) is available or note fallback
- [ ] Generate a `task_id` in format `T-YYYY-MM-DD-NNN`
- [ ] Create `.aifirst/runs/<task_id>/` directory structure
- [ ] Open G0-plan.md and populate all sections before any execution

### Execution Order

```
For each file in pilot corpus (priority 1→6):
  Phase 0: Generate CFG artifact
    → FAIL: log, skip file, continue to next
  Phase 1: Translate to MD
    → FAIL: log, attempt once with chunked prompt, then skip
  Phase 2: Run T01 → T02 → T02-R → T03 → T04 → T05
    → FAIL at T01/T02/T02-R: log BLOCKED, skip file
    → FAIL at T03: log score, attempt retry with targeted re-prompt, then skip
    → FAIL at T04: log score, capture trajectory pairs, continue (T04 FAIL does not block)
    → T05 unavailable: log DEFERRED, continue

After all 6 files processed:
  Phase 3: Produce candidate gold files + review checklists
    → STOP: Do not proceed to Phase 4 without human sign-off on gold files

Human sign-off received:
  Phase 4: Fine-tune
  Phase 5: Re-validate + SWE-bench
  Produce proof document table
```

### What to Report at Completion

Produce a `COMPLETION-REPORT.md` at the root of the repo with:
1. Files successfully translated (T01–T03 PASS)
2. Files blocked (with tier and reason)
3. T04 scores per file and paragraph
4. Number of trajectory pairs captured
5. Novel failure modes not in §8 (append to `failure_modes.log`)
6. Human review agenda: list of items requiring manual verification
7. Estimated Phase 3 review time per file
8. Readiness assessment for Phase 4 (go/no-go with justification)

---

## 10. Knowledge Graph Target State

The long-term objective this pipeline serves. Not required for proof-of-concept, but every schema decision was made with this target in mind.

```cypher
// Target graph schema (Neo4j)
(Program {program_id, business_domain, subtype, schema_version, aifirst_task_id})
  -[:CALLS {condition, call_type}]->(Program)
  -[:USES_COPYBOOK]->(Copybook {name, sha})
  -[:READS|WRITES|DELETES {crud}]->(VsamFile {ddname, organization})
  -[:HAS_RULE {reachable}]->(BusinessRule {id, rule, rule_type, confidence})
  -[:HAS_DATA_ITEM {dead_code_flag}]->(DataItem {name, picture, semantic})
  -[:HAS_PARAGRAPH {reachable, goto_flag}]->(Paragraph {name, summary})
```

Key query: *"Which programs contain business rules governing CUSTFILE access, and are any of those rules currently unreachable?"*

```cypher
MATCH (p:Program)-[:READS|WRITES]->(f:VsamFile {ddname: 'CUSTFILE'})
MATCH (p)-[:HAS_RULE]->(r:BusinessRule)
RETURN p.program_id, r.rule, r.reachable, r.confidence
ORDER BY r.reachable DESC, r.confidence DESC
```

When ≥10 pilot files pass T04, load into Neo4j using the node model above and run this query as the proof-of-concept knowledge graph demo.

---

## Version History

| Version | Date | Author | Notes |
|---------|------|--------|-------|
| 1.0.0 | 2026-04-23 | Mark Snow | Initial master architecture — full autonomous implementation spec with pre-flight checklist, failure modes table, execution order, and completion report requirements |
