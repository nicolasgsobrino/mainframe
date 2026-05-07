---
schema_version: "cobol-md/1.0"
document: "COBOL-MD-SCHEMA"
version: "1.0.2"
status: "ACTIVE"
changelog:
  - version: "1.0.0"
    date: "2026-04-23"
    author: "Mark Snow"
    notes: "Initial schema — core fields, validation tiers, knowledge graph edges"
  - version: "1.0.1"
    date: "2026-04-23"
    author: "Mark Snow"
    notes: "Added business_domain (Grok) and subtype (Grok) as top-level required fields"
  - version: "1.0.2"
    date: "2026-04-23"
    author: "Mark Snow"
    notes: "Gemini integration: redefines_interpretations[], dead_code_flag, cfg_source ref, T02-R subcheck"
---

# COBOL-MD Schema v1.0.2

## Purpose

This schema defines the **required YAML front-matter structure** for every `.md` file produced by the COBOL→English middle-layer translation pipeline. Each translated file is a **semantic artifact**, not a decorated source file. The raw COBOL source is never embedded in the MD output — it remains in `app/cbl/`. The MD file is the independent English representation, designed for knowledge graph ingestion, LLM reasoning, and intelligence layer construction.

> **Design principle:** If a business rule, data item, or procedure paragraph exists in the COBOL source, it MUST appear in the MD file. Absence = T02/T03 validation failure.

> **Gemini integration (v1.0.2):** Three enhancements from Gemini research: (1) `cfg_source` links each translation to its pre-processed Control Flow Graph artifact from Phase 0; (2) `redefines_interpretations[]` explicitly captures both type interpretations of REDEFINES clauses and the runtime condition that selects between them — a documented production failure mode; (3) `dead_code_flag` and `reachable` mark unreachable paragraphs identified by static analysis so the knowledge graph can filter noise.

---

## Full Schema

```yaml
---
# ── Identity ──────────────────────────────────────────────────────────────────
schema_version: "cobol-md/1.0"          # REQUIRED — always "cobol-md/1.0"
program_id: "CBCUS01C"                   # REQUIRED — matches PROGRAM-ID in source
source_file: "app/cbl/CBCUS01C.cbl"     # REQUIRED — repo-relative path
source_sha: "88a99d7f..."               # REQUIRED — git blob SHA of source at translation time
translation_date: "2026-04-23"          # REQUIRED — ISO-8601 date
translating_agent: "qwen3-235b-a22b"    # REQUIRED — exact model identifier
aifirst_task_id: "T-2026-04-23-001"     # REQUIRED — links to /aifirst run log
cfg_source: "validation/structure/CBCUS01C_cfg.json"  # REQUIRED — Phase 0 CFG artifact path

# ── Classification (Grok-integrated v1.0.1) ───────────────────────────────────
business_domain: "Account Management"   # REQUIRED — knowledge graph cluster label
                                         # Valid values:
                                         # Account Management | Transaction Processing |
                                         # Customer Management | Authorization |
                                         # Reporting | Administration | Utility | Menu

subtype: "Batch"                         # REQUIRED — graph partitioning key
                                         # Valid values:
                                         # CICS-Online | Batch | Utility | Menu | Copybook

# ── Structural Metadata ───────────────────────────────────────────────────────
author: ""                               # from AUTHOR paragraph, null if absent
date_written: ""                         # from DATE-WRITTEN paragraph, null if absent
lines_of_code: 0                         # total non-blank, non-comment lines
divisions:
  identification: true
  environment: true
  data: true
  procedure: true
environment:
  compiler: "IBM Enterprise COBOL"       # IBM Enterprise COBOL | GnuCOBOL | MicroFocus
  target: "CICS/VSAM"                    # CICS/VSAM | Batch/VSAM | Batch/DB2 | Utility
  runtime: "z/OS"                        # z/OS | AWS Blu Age | other

# ── Graph Edges ───────────────────────────────────────────────────────────────
calls_to:                                # REQUIRED — directed outbound call edges
  - program: "CBCUS01C"
    condition: "WS-CUST-STATUS = 'ACTIVE'"
    call_type: "STATIC"                  # STATIC | DYNAMIC | EXEC CICS LINK | EXEC CICS XCTL
called_by:                               # REQUIRED — inbound call edges (reverse index)
  - "COACTUPC"
copybooks_used:                          # REQUIRED — shared schema edges
  - name: "CVACTREC"
    path: "app/cpy/CVACTREC.cpy"
    sha: "abc123..."

# ── File I/O ──────────────────────────────────────────────────────────────────
file_control:
  - ddname: "CUSTFILE"
    organization: "INDEXED"              # INDEXED | SEQUENTIAL | RELATIVE
    access: "DYNAMIC"                    # SEQUENTIAL | RANDOM | DYNAMIC
    record_key: "WS-CUSTOMER-ID"
    crud: ["READ", "WRITE", "DELETE"]    # CREATE | READ | UPDATE | DELETE

# ── CICS (online programs only) ───────────────────────────────────────────────
cics_commands: []                        # list of EXEC CICS commands used
transaction_ids: []                      # CICS transaction IDs this program services

# ── Data Layer ────────────────────────────────────────────────────────────────
data_items:                              # REQUIRED — every 01-level working storage item
  - name: "WS-CUSTOMER-ID"
    level: 01
    picture: "X(10)"
    usage: null                          # COMP | COMP-3 | BINARY | DISPLAY | null
    value: null
    redefines: null                      # name of item this redefines, or null
    redefines_interpretations: []        # REQUIRED when redefines != null — see T02-R below
    dead_code_flag: false                # true if static analysis marks this item unreachable
    semantic: "Unique 10-char identifier linking to CUSTFILE VSAM index key"

  # Example of a REDEFINES item (Gemini v1.0.2):
  # - name: "WS-TRANS-DATA-CREDIT"
  #   level: 01
  #   picture: "9(13)V99 COMP-3"
  #   redefines: "WS-TRANS-DATA"
  #   redefines_interpretations:
  #     - condition: "WS-TRANS-TYPE = 'CREDIT'"
  #       interpreted_as: "Packed decimal amount, 15 digits, 2 decimal places"
  #       encoding: "COMP-3"
  #     - condition: "WS-TRANS-TYPE = 'DEBIT'"
  #       interpreted_as: "Character string account reference, 15 chars"
  #       encoding: "DISPLAY"
  #   dead_code_flag: false
  #   semantic: "Dual-type transaction data field — interpretation selected at runtime by WS-TRANS-TYPE"

# ── Procedure Paragraphs ──────────────────────────────────────────────────────
procedure_paragraphs:                    # REQUIRED — every paragraph/section in PROCEDURE DIVISION
  - name: "0100-INIT"
    reachable: true                      # false = dead code per Phase 0 static analysis
    performs: ["0200-READ-CUST"]         # paragraphs this paragraph PERFORMs
    goto_targets: []                     # GOTO targets (should be empty after CFG flattening)
    summary: "Initializes working storage and opens CUSTFILE for dynamic access"

# ── Business Rules ────────────────────────────────────────────────────────────
business_rules:                          # REQUIRED — implicit rules surfaced from conditional logic
  - id: "BR-001"
    rule: "A customer record cannot be deleted if WS-CUST-STATUS is not 'INACTIVE'"
    source_paragraph: "1200-DELETE-VALIDATE"
    rule_type: "guard"                   # guard | transform | lookup | audit | display
    confidence: "high"                  # high | medium | low
    reachable: true                      # false if source_paragraph is dead code

# ── Validation Status (populated by /aifirst G3 — not by translating agent) ──
validation:
  t01_schema_valid: null                 # true | false | null (PENDING)
  t02_structural_complete: null          # true | false | null
  t02r_redefines_complete: null          # true | false | null — T02-R subcheck (v1.0.2)
  t03_functional_score: null             # 0.0–1.0
  t04_semantic_score: null              # 0.0–1.0
  t05_regression_pass: null
  overall: "PENDING"                    # PENDING | PASS | FAIL
---
```

---

## Field Reference

### Identity Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `schema_version` | ✅ | string | Always `"cobol-md/1.0"` |
| `program_id` | ✅ | string | Matches `PROGRAM-ID` in source |
| `source_file` | ✅ | string | Repo-relative path to `.cbl` |
| `source_sha` | ✅ | string | Git blob SHA — enables exact source pinning |
| `translation_date` | ✅ | ISO-8601 | Date translation was produced |
| `translating_agent` | ✅ | string | Model that produced this file |
| `aifirst_task_id` | ✅ | string | Links to `/aifirst` run log |
| `cfg_source` | ✅ | string | Path to Phase 0 CFG JSON artifact |

### Classification Fields *(Grok v1.0.1)*

| Field | Required | Valid Values | Graph Role |
|-------|----------|-------------|------------|
| `business_domain` | ✅ | Account Management, Transaction Processing, Customer Management, Authorization, Reporting, Administration, Utility, Menu | **Cluster label** — community detection anchor |
| `subtype` | ✅ | CICS-Online, Batch, Utility, Menu, Copybook | **Partition key** — CICS vs. Batch subgraph |

### Data Layer Fields *(Gemini v1.0.2)*

#### `redefines_interpretations[]`

Required whenever `redefines != null`. Captures **both type interpretations** of a REDEFINES clause and the runtime condition that selects between them. Omitting this field on a REDEFINES item = T02-R failure.

This addresses a documented production failure mode identified in Gemini's research: a single memory address interpreted as different data types depending on runtime flags. When an LLM misses this, it writes semantically incorrect translations that appear structurally complete but corrupt business logic.

Subfields:
- `condition` — the runtime flag or field value that activates this interpretation
- `interpreted_as` — plain English description of what the memory represents under this condition
- `encoding` — storage encoding: COMP-3 | COMP | BINARY | DISPLAY

#### `dead_code_flag`

Boolean. Set to `true` by the Phase 0 static reachability analysis (Cobol-REKT) when an item is defined but never referenced by any reachable paragraph. Dead items are still translated (for completeness) but flagged so the knowledge graph can exclude them from business rule queries.

### Procedure Paragraphs Field *(Gemini v1.0.2)*

`procedure_paragraphs[]` is a new required array parallel to the prose Procedure Logic section. Each entry is a machine-readable record of one paragraph:

- `name` — paragraph/section name exactly as in COBOL source
- `reachable` — `false` if Phase 0 static analysis marks it unreachable (dead code)
- `performs` — list of paragraphs this paragraph PERFORMs (used to build call sub-graph)
- `goto_targets` — GOTO targets; should be empty after CFG flattening; non-empty = flag for review
- `summary` — one-sentence English summary

This is the machine-readable complement to the prose Procedure Logic section that T02 diffs against.

### T02-R Subcheck *(Gemini v1.0.2)*

T02-R is a new mandatory subcheck within T02. For every `data_items[]` entry where `redefines != null`:
1. Verify `redefines_interpretations[]` is present and non-empty
2. Verify at least 2 interpretation entries exist (minimum: the two interpretations)
3. Verify each entry has `condition`, `interpreted_as`, and `encoding` populated
4. Verify the `condition` values reference an actual field present in `data_items[]`

T02-R failure = T02 failure. No threshold; absolute.

### Business Rules Field

`business_rules[]` is the **highest-value field** for the knowledge graph. These are implicit rules buried in conditional logic — they exist nowhere in any documentation, only in the COBOL source.

`rule_type` vocabulary:
- `guard` — blocks an operation if a condition isn't met
- `transform` — converts or reformats data
- `lookup` — retrieves from a reference file or table
- `audit` — writes a record for compliance/logging
- `display` — controls what the user sees

`reachable: false` on a business rule means it originates in dead code — it should be preserved in the MD for historical completeness but excluded from active knowledge graph queries.

### Validation Field

The `validation` block is populated exclusively by the `/aifirst` G3 gate. The translating agent cannot self-certify. `overall: "PASS"` requires all tier scores to meet thresholds, including `t02r_redefines_complete: true`.

---

## Corpus Map: CardDemo Pilot Files

| File | Size | `business_domain` | `subtype` | Tier | Run Order |
|------|------|------------------|-----------|------|-----------|
| `COBSWAIT.cbl` | 2KB | Utility | Utility | S | 1 |
| `CBCUS01C.cbl` | 7KB | Customer Management | Batch | S | 2 |
| `COSGN00C.cbl` | 10KB | Administration | CICS-Online | M | 3 |
| `COMEN01C.cbl` | 12KB | Administration | Menu | M | 4 |
| `CBACT01C.cbl` | 17KB | Account Management | Batch | M | 5 |
| `CBTRN01C.cbl` | 18KB | Transaction Processing | Batch | L | 6 |
| `CBTRN02C.cbl` | 59KB | Transaction Processing | Batch | L | Post-FT |
| `COACTUPC.cbl` | 182KB | Account Management | CICS-Online | XL | Post-FT |

---

## Output File Convention

```
translations/
  baseline/          ← pre-fine-tune run
  post-finetune/     ← post-fine-tune run
  gold/              ← human-verified training pairs
```

Diff between `baseline/` and `post-finetune/` = proof of improvement.
Diff between `post-finetune/` and `gold/` = residual error after fine-tuning.

---

## T02 + T02-R Structural Completeness Tests

```bash
# Phase 0: extract CFG and structure from source
cobc -fsyntax-only -fdiagnostics-format=json CBCUS01C.cbl 2>&1 | \
  python3 scripts/extract_structure.py > validation/structure/CBCUS01C_structure.json

# Cobol-REKT CFG + reachability
java -jar cobol-rekt.jar --cfg CBCUS01C.cbl \
  --output validation/structure/CBCUS01C_cfg.json

# T02 structural diff
python3 scripts/validate_t02.py \
  --source-structure validation/structure/CBCUS01C_structure.json \
  --translation translations/baseline/CBCUS01C.md

# T02-R REDEFINES subcheck
python3 scripts/validate_t02r.py \
  --source-structure validation/structure/CBCUS01C_structure.json \
  --translation translations/baseline/CBCUS01C.md
```

T02 + T02-R failures are absolute — no threshold, no partial credit.

---

## Knowledge Graph Node Model

```
(Program {program_id, business_domain, subtype})
  -[:CALLS {condition, call_type}]->(Program)
  -[:USES_COPYBOOK]->(Copybook {name})
  -[:READS | WRITES | DELETES]->(VsamFile {ddname})
  -[:HAS_RULE {reachable}]->(BusinessRule {id, rule_type, confidence})
  -[:HAS_DATA_ITEM {reachable}]->(DataItem {name, picture, semantic})
  -[:HAS_PARAGRAPH {reachable}]->(Paragraph {name, goto_targets})
```

`reachable: false` on any edge → node exists in graph but excluded from business queries by default.

Query example — active business rules on CUSTFILE only:
```cypher
MATCH (p:Program)-[:READS|WRITES]->(f:VsamFile {ddname: 'CUSTFILE'})
MATCH (p)-[:HAS_RULE {reachable: true}]->(r:BusinessRule)
RETURN p.program_id, p.business_domain, r.rule, r.confidence
ORDER BY p.business_domain
```

---

## Version History

| Version | Date | Author | Notes |
|---------|------|--------|-------|
| 1.0.0 | 2026-04-23 | Mark Snow | Initial schema |
| 1.0.1 | 2026-04-23 | Mark Snow | Added `business_domain` and `subtype` (Grok) |
| 1.0.2 | 2026-04-23 | Mark Snow | Gemini: `cfg_source`, `redefines_interpretations[]`, `dead_code_flag`, `procedure_paragraphs[]`, T02-R subcheck, `reachable` on business rules and paragraphs |
