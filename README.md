---
document_type: AI-First Living README
project_name: COBOL-MD-PIPELINE (CardDemo Modernization)
current_phase: Phase 3 - Batch Translation (8 of ~40 programs complete)
system_status: PIPELINE_OPERATIONAL
target_architecture: 3-Pass Deterministic + Bounded-LLM DAG
cleared_validation_gates:
  - T01_YAML_PARSE: true
  - T02_COMPLETENESS: true
  - T02-R_REDEFINES_BOUNDS: true
  - T03_STRUCTURAL_MATCH: true
  - PASS1_SELFTEST: true
  - PASS2_TOKEN_BUDGETS: true
  - GATE_PIPELINE: true
pending_action: RUN_BATCH_REMAINING_32_PROGRAMS
---

# AWS CardDemo Modernization: COBOL → Verified English MD Pipeline

## Agent Scope Discipline

Before any agent (local or cloud) makes changes on any branch, it
MUST read [BRANCH-SCOPE.md](./BRANCH-SCOPE.md) first. Plan files like
`DEMO-SPRINT-PLAN.md` are advisory only. Branch-scope rules are
authoritative.

## What This Project Does

This pipeline translates each COBOL program in the AWS CardDemo mainframe application into a **verified, human-readable English Markdown file with YAML front-matter**. Each output `.md` file is a structured specification that describes:

- What the program does (purpose and business function)
- Every data field it reads and writes (with memory layout)
- Its paragraph-by-paragraph logic in plain English
- Its call graph (which paragraphs call which)
- Its CICS screen navigation state machine (for online programs)
- Dead code paragraphs that are never reached

These `.md` files are the **verified intermediate layer** — usable by cloud architects, modernization teams, or downstream code-generation pipelines without repeating the comprehension work.

**Current status:** 8 of ~40 programs have completed, gate-verified `.md` files. The pipeline is fully operational for batch processing the remaining 32.

---

## How This Differs From Existing Tools

Commercial tools like IBM watsonx Code Assistant, AWS Transform for Mainframe, and Micro Focus Enterprise Analyzer either:
- **Transpile** — convert COBOL syntax to Java/Python line-for-line, producing code a developer still cannot read
- **Summarize** — produce an LLM narrative with no verification, generating plausible-sounding but untrustworthy documentation

This pipeline does neither. It produces **proposition-level English claims**, each traceable to a specific source line, with a confidence score and an automated gate that fails any document claiming a paragraph or data field that does not exist in the COBOL source. No commercial tool provides this anti-hallucination guarantee.

The academic consensus (Arigela & Virwal 2025, AlphaTrans 2024, IBM ICSE 2025) confirms: LLMs alone fail at repository-scale COBOL. The correct architecture is static analysis first, bounded LLM second, automated verification third. This pipeline implements exactly that.

---

## Repository Layout

```
app/cbl/                                  COBOL source — READ ONLY, never modify
app/copybooks/                            COPY member sources
scripts/
  pass1_annotate.py                       Pass 1 — deterministic statement annotator
  pass2_llm.py                            Pass 2 — LLM payload builder
  pass2_template.py                       Pass 2 — template renderer for simple verbs
  pass2_override.py                       Pass 2 — manual overrides
  pass3_synthesize.py                     Pass 3 — MD renderer
  validate_t01.py .. validate_t03.py      Frozen structural validators (do not modify)
  extract_byte_layout.py                  Data layout extractor
  extract_cfg_summary.py                  CFG summarizer (includes L01 data-item parser)
  extract_fallthrough.py                  Fallthrough path extractor
  extract_file_control.py                 FILE CONTROL section extractor
  extract_paragraph_io.py                 Paragraph I/O extractor
translations/
  gold-candidate/*.md                     Gate-verified completed translations
  baseline/*.md                           v1.0 hand-verified intermediate MD
validation/
  structure/*_cfg.json                    Cobol-REKT static analysis output (CFG + L01 items)
  pass1/*_annotations.json               Pass 1 statement annotation output
  pass1/*_phantoms.json                   Pass 1 filtered phantom paragraph log
  pass2/*_propositions.json              Pass 2 proposition set
  pass2/*_llm_requests.jsonl             Pass 2 LLM API call queue
  claims/                                 extract_md_claims output
  ground_truth/                           extract_ground_truth output
  logs/                                   Gate run logs (timestamped)
  cobol_vocab.py                          Single source of truth for COBOL reserved words
  extract_ground_truth.py                 Gate: extract CFG facts
  extract_md_claims.py                    Gate: extract MD claims
  gate_compare.py                         Gate: compare claims vs ground truth
  lint_md.py                              Pre-commit MD linter
.aifirst/runs/T-*/run.log               Per-task deterministic event log
```

---

## The 3-Pass Translation Pipeline

Every COBOL program passes through four sequential stages. Zero LLM calls happen until Stage 2, and even there the LLM is bounded to one statement at a time with all context pre-computed.

### Stage 0 — Static Analysis (Cobol-REKT)
**Tool:** `smojol-cli` (Cobol-REKT RC8)  
**Input:** `app/cbl/PROGNAME.cbl`  
**Output:** `validation/structure/PROGNAME_cfg.json`

Extracts every paragraph, data item, and PERFORM call relationship from the source without any inference. This JSON is the ground truth that all downstream stages use.

```json
{
  "paragraphs": [{"name": "3000-READ-CARD", "reachable": true}],
  "data_items":  [{"name": "WS-CARD-NUM", "level": "05", "picture": "X(16)"}],
  "call_graph":  [{"from": "1000-MAIN", "to": "3000-READ-CARD"}]
}
```

---

### Stage 1 — Annotation (Pass 1)
**Script:** `scripts/pass1_annotate.py`  
**Input:** `.cbl` source + `_cfg.json`  
**Output:** `validation/pass1/PROGNAME_annotations.json`

Walks every line of the preprocessed source (`cobc -E`) and emits one annotation record per statement:

```json
{
  "seq": 42,
  "paragraph": "3000-READ-CARD",
  "line": 387,
  "verb": "READ",
  "operands": ["CARD-FILE"],
  "operand_types": ["working-storage"],
  "cfg_branch_context": null,
  "cfg_edges_in": ["1000-MAIN:seq41"],
  "cfg_edges_out": ["3100-HANDLE-ERROR:seq55"],
  "cics_branch": false,
  "confidence_floor": 0.9
}
```

**Zero LLM. Deterministic and reproducible.**

Active patches (all merged to main as of 2026-04-30):
- **P1** — Real paragraph call-graph edges replace seq±1 placeholders
- **P2** — Data inventory built from `cobc -E` expanded source (catches COPY member fields)
- **P3** — IF/EVALUATE scope depth tracked to clear branch context after END-IF/END-EVALUATE
- **P5** — CICS RETURN/XCTL/LINK/HANDLE/ABEND detected as branch points

**Prerequisite:** GnuCOBOL 3.2 must be installed and `cobc` on PATH. Windows users: download the pre-built binary from Arnold Trembley's distribution at https://sourceforge.net/projects/gnucobol/files/gnucobol/3.2/ and add the `bin\` folder to your user PATH.

Verify before running:
```powershell
cobc --version
python scripts/pass1_annotate.py --selftest
# Expected: {"selftest": "PASS", ...}
```

---

### Stage 2 — Proposition Building (Pass 2)
**Scripts:** `scripts/pass2_llm.py` + `scripts/pass2_template.py`  
**Input:** `_annotations.json`  
**Output:** `validation/pass2/PROGNAME_llm_requests.jsonl`

Simple statements (MOVE, ADD, OPEN, CLOSE) are rendered to English via deterministic templates — no LLM needed. Complex statements (IF, EVALUATE, EXEC CICS, CALL) are packaged as bounded LLM requests with full annotation context:

```json
{
  "temperature": 0,
  "seed": 42,
  "model": "gpt-4o-2024-08-06",
  "max_tokens_ceiling": 700,
  "verb_token_budgets": {
    "EVALUATE": 700, "EXEC CICS": 600, "EXEC SQL": 600,
    "IF": 500, "CALL": 500, "MOVE CORRESPONDING": 500
  }
}
```

Active patches:
- **P4** — Per-verb token budgets prevent PARTIAL truncation loops on complex EVALUATE blocks

---

### Stage 3 — Synthesis (Pass 3)
**Script:** `scripts/pass3_synthesize.py`  
**Input:** LLM responses merged with propositions  
**Output:** `translations/gold-candidate/PROGNAME.md`

Renders the final `.md` with YAML front-matter and structured English sections:

```yaml
---
program_id: COSGN00C
source_file: app/cbl/COSGN00C.cbl
paragraphs_total: 18
paragraphs_reachable: 15
data_items: 47
translation_confidence: 0.87
gate_status: PASS
---
```

Followed by: Purpose, Data Layout, Paragraph Logic, Call Graph, CICS Screen Flow, Dead Code.

---

### Stage 4 — Gate Verification
**Scripts:** `validation/extract_ground_truth.py` → `extract_md_claims.py` → `gate_compare.py`  
**Output:** `validation/logs/gate_TIMESTAMP.log`

Automatically compares every claim in the `.md` against the CFG ground truth. Exits 1 (FAIL) if any paragraph is hallucinated, any data field is invented, or any call target does not exist in the source. **A program is not done until this gate passes.**

Gate run sequence:
```powershell
py -3 validation/extract_cfg_summary.py --all
py -3 validation/extract_ground_truth.py
py -3 validation/extract_md_claims.py
py -3 validation/gate_compare.py
```

Expected output for a clean batch:
```
-- Gate Summary ------------------------------------------------
  PASS  CBACT01C
  PASS  CBACT02C
  PASS  CBACT03C
  PASS  CBCUS01C
  PASS  CBTRN01C
  PASS  COBSWAIT
  PASS  COMEN01C
  PASS  COSGN00C
  8/8 programs passed
----------------------------------------------------------------
```

---

## Completed Translations

| Program | Description | Size | Gate |
|---|---|---|---|
| [CBACT01C.md](translations/gold-candidate/CBACT01C.md) | Account file batch processor | 41 KB | ✅ PASS |
| [CBACT02C.md](translations/gold-candidate/CBACT02C.md) | Account cross-ref batch processor | 17 KB | ✅ PASS |
| [CBACT03C.md](translations/gold-candidate/CBACT03C.md) | Card cross-ref batch processor | 22 KB | ✅ PASS |
| [CBCUS01C.md](translations/gold-candidate/CBCUS01C.md) | Customer file processor | 22 KB | ✅ PASS |
| [CBTRN01C.md](translations/gold-candidate/CBTRN01C.md) | Daily transaction processor | 38 KB | ✅ PASS |
| [COBSWAIT.md](translations/gold-candidate/COBSWAIT.md) | Wait utility | 4 KB | ✅ PASS |
| [COMEN01C.md](translations/gold-candidate/COMEN01C.md) | Main menu handler | 31 KB | ✅ PASS |
| [COSGN00C.md](translations/gold-candidate/COSGN00C.md) | Sign-on screen (CICS) | 26 KB | ✅ PASS |

**Remaining:** ~32 programs pending. Next target: CBACT04C (account update batch) and COCRDUPC (card update screen).

---

## Gate Tooling — Recent Fixes

These fixes to the validation pipeline were merged as part of the `fix/gate-failures-cbact01c-02c-03c` branch and should be included in the main merge:

| Fix | What it addressed |
|---|---|
| `extract_cfg_summary.py` — L01 data-item parser | Scans `DATA DIVISION` for `01`-level declarations and writes them to `_cfg.json` under `data_items`; without this, every MD `data_items` entry was flagged as hallucinated |
| `extract_cfg_summary.py` — tightened `is_paragraph_node()` | Rejects all COBOL verb-prefixed CFG labels (e.g., `MOVECARDFILE-ST`, `PERFORMUNTILEND`, `GOBACK`) that Cobol-REKT emits as synthetic CFG nodes but are not user-defined paragraphs |
| CBACT01C.md | Removed hallucinated paragraphs `END-IF`, `END-PERFORM`, `GOBACK`, `VB2-ACCT-ID`, `WS-REISSUE-DATE` from `procedure_paragraphs` |
| CBACT02C.md | Fixed missing `---` YAML frontmatter block; removed hallucinated `END-PERFORM` paragraph and `CARD-RECORD` data item |
| CBACT03C.md | Removed hallucinated `CARD-XREF-RECORD` data item |

---

## Per-Program Recipe for Batch Agent

Run this sequence for each COBOL program. All steps must pass before moving to the next program.

### Prerequisites (verify once before starting batch)
```powershell
cobc --version                   # GnuCOBOL 3.2+
python --version                 # Python 3.10+
smojol --version                 # Cobol-REKT RC8 for Stage 0
python scripts/pass1_annotate.py --selftest  # must return PASS
```

### Stage 0 — Generate CFG
```powershell
smojol analyze app/cbl/PROGNAME.cbl --out validation/structure/PROGNAME_cfg.json
```

### Stage 1 — Annotate
```powershell
python scripts/pass1_annotate.py `
  --src app/cbl/PROGNAME.cbl `
  --cfg validation/structure/PROGNAME_cfg.json `
  --program-id PROGNAME `
  --out validation/pass1/PROGNAME_annotations.json `
  --phantoms-out validation/pass1/PROGNAME_phantoms.json
```
Verify stdout shows `cfg_edges_resolved > 0` and `cfg_edges_unresolved == 0` before proceeding.

### Stage 2 — Build Propositions
```powershell
python scripts/pass2_llm.py `
  --annotations validation/pass1/PROGNAME_annotations.json `
  --program-id PROGNAME `
  --out validation/pass2/PROGNAME_llm_requests.jsonl
```
Verify envelope shows `max_tokens_ceiling: 700` and `verb_token_budgets` present.

### Stage 3 — Synthesize MD
```powershell
python scripts/pass3_synthesize.py `
  --requests validation/pass2/PROGNAME_llm_requests.jsonl `
  --program-id PROGNAME `
  --out translations/gold-candidate/PROGNAME.md
```

### Stage 4 — Gate Check
```powershell
py -3 validation/extract_cfg_summary.py --all
py -3 validation/extract_ground_truth.py
py -3 validation/extract_md_claims.py
py -3 validation/gate_compare.py
# Exit 0 = PASS. Exit 1 = FAIL — fix MD before committing.
```

### Baseline Verification (run before starting any batch)
```powershell
# Confirm all 8 completed programs still pass before adding more
py -3 validation/gate_compare.py
# All 8 must show PASS
```

---

## Hard Constraints for Agent Loop

1. **No edits to `app/cbl/**`** — COBOL source is the immutable ground truth.
2. **No edits to `scripts/validate_t0*.py`** — structural validators are frozen.
3. **No LLM calls for structural/bounds decisions** — use CFG and COBOL source deterministically.
4. **Gate must pass before a program is considered done** — `gate_compare.py` exit 0 is the acceptance criterion.
5. **Every task run produces `.aifirst/runs/T-<id>/run.log`** with before/after SHAs for reproducibility.
6. A program's `.md` is **not promoted to gold-candidate** until `gate_status: PASS` is confirmed.

---

## Validation Gate Definitions

| Gate | What it proves | Enforcer |
|---|---|---|
| T01 | Every MD parses as YAML and matches `schema_version: cobol-md/1.0` | `validate_t01.py` |
| T02 | Every field in the CFG is present in the MD (completeness) | `validate_t02.py` |
| T02-R | Every `redefines_interpretations[*].condition` references a CFG-known field | `validate_t02r.py` |
| T03 | MD structural shape matches CFG hierarchy (01-levels, groups, OCCURS) | `validate_t03.py` |
| GATE | No hallucinated paragraphs, data fields, or call targets in the MD | `gate_compare.py` |
| LINT | No scope terminator names used as paragraph names in the MD | `lint_md.py` |

---

## Why the Hybrid Pipeline

Recent peer-reviewed work converges on the same finding: LLMs alone fail at repository-scale COBOL, but a hybrid pipeline where static analysis does structural heavy lifting and LLMs do bounded semantic narrative is dramatically more reliable:

- Arigela & Virwal (2025) report combining flowcharts with vector-DB chunking reduces LLM hallucination rates by **70%** and raises BLEU by **15.8 points** in banking-domain pilots ([IJAIT 2025](https://aircconline.com/ijait/V15N5/15525ijait01.pdf)).
- AlphaTrans (ACM 2024) achieves 96.4% syntactic correctness at repository scale where direct LLM translation collapses ([ACM](https://dl.acm.org/doi/10.1145/3729379)).
- IBM ICSE 2025 emphasizes LLM translations "cannot be trusted" without automated equivalence checking ([FSE 2024](https://dl.acm.org/doi/10.1145/3691620.3695365)).
- Gandhi et al. (2024) show direct COBOL→Java translation hits only 60% execution accuracy; adding execution-guided refinement raises it to **81.99%** ([ACM 2024](https://dl.acm.org/doi/10.1145/3643795.3648388)).

This pipeline implements the same consensus: static analysis eliminates the classes of error LLMs demonstrably make, and only then hands structured input to the LLM for narrative generation.

---

## Project Context: AWS CardDemo

CardDemo is an open-source sample mainframe application published by AWS in December 2022 for mainframe modernization experimentation ([AWS Open Source Blog](https://aws.amazon.com/blogs/opensource/introducing-open-source-aws-carddemo-for-mainframe-modernization/)). AWS's own guidance uses CardDemo as the reference workload for AWS Transform for Mainframe. This repository takes a different approach: instead of emitting Java directly, we emit a **verified intermediate semantic layer** (Markdown + YAML, validated against the CFG) so any downstream consumer can plug in without re-doing the comprehension work.

---

## References

- [AWS Open Source Blog — *Introducing Open Source AWS CardDemo* (2022)](https://aws.amazon.com/blogs/opensource/introducing-open-source-aws-carddemo-for-mainframe-modernization/)
- [AWS Prescriptive Guidance — *Modernize CardDemo using AWS Transform*](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/modernize-carddemo-mainframe-app.html)
- Arigela & Virwal — [*Prompt Engineering Pipelines for Legacy Modernization*, IJAIT 2025](https://aircconline.com/ijait/V15N5/15525ijait01.pdf)
- Ibrahimzada et al. — [*AlphaTrans*, ACM 2024](https://dl.acm.org/doi/10.1145/3729379)
- Dau et al. — [*XMainframe*, arXiv:2408.04660](https://arxiv.org/abs/2408.04660)
- Kumar, Saha et al. — [*Automated Validation of COBOL to Java Transformation*, FSE 2024](https://dl.acm.org/doi/10.1145/3691620.3695365)
- Gandhi et al. — [*Translation of Low-Resource COBOL to Logically Correct and Readable Java*, ACM 2024](https://dl.acm.org/doi/10.1145/3643795.3648388)
- Diggs et al. — [*Leveraging LLMs for Legacy Code Modernization*, arXiv:2411.14971](https://arxiv.org/abs/2411.14971)
- [IN-COM — *How to Find Buffer Overflows in COBOL Using Static Analysis* (2025)](https://www.in-com.com/blog/how-to-find-buffer-overflows-in-cobol-using-static-analysis/)
- [CB Insights — *The generative AI market map*](https://app.cbinsights.com/research/generative-ai-startups-market-map/)
