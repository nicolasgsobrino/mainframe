---
schema_version: "cobol-md/1.0"
program_id: "COBSWAIT"
source_file: "app/cbl/COBSWAIT.cbl"
source_sha: "7957347717cf04be2dc4f5be24aa94668cf780ab"
translation_date: "2026-04-23"
translating_agent: "claude-sonnet-4.6 (Perplexity Computer autonomous COBOL modernization agent)"
aifirst_task_id: "T-2026-04-23-001"
cfg_source: "validation/structure/COBSWAIT_cfg.json"

business_domain: "Utility"
subtype: "Utility"

author: null
date_written: null
lines_of_code: 8
divisions:
  identification: true
  environment: true
  data: true
  procedure: true
environment:
  compiler: "IBM Enterprise COBOL"
  target: "Batch/VSAM"
  runtime: "z/OS"

calls_to:
  - program: "MVSWAIT"
    condition: "unconditional"
    call_type: "STATIC"
called_by: []
copybooks_used: []

file_control: []

cics_commands: []
transaction_ids: []

data_items:
  - name: "MVSWAIT-TIME"
    level: 1
    picture: "9(8)"
    usage: "COMP"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Binary (COMP) wait duration in centiseconds supplied to the MVSWAIT system service. Populated from PARM-VALUE at program start."
  - name: "PARM-VALUE"
    level: 1
    picture: "X(8)"
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Character parameter string accepted from SYSIN; carries the caller-supplied wait duration before it is moved to the binary MVSWAIT-TIME field."

procedure_paragraphs:
  - name: "MAIN-INLINE"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Implicit main procedure (the PROCEDURE DIVISION contains no named paragraphs): accept the parameter from SYSIN, move it into the binary wait-time field, call the MVSWAIT system service, and stop the run."

business_rules:
  - id: "BR-001"
    rule: "Program accepts a single ASCII parameter from SYSIN and reinterprets it as an 8-digit binary wait duration passed to MVSWAIT."
    source_paragraph: "MAIN-INLINE"
    rule_type: "transform"
    confidence: "high"
    reachable: true
  - id: "BR-002"
    rule: "Control returns to the operating system immediately after MVSWAIT returns; there is no error handling, retry, or alternate exit path."
    source_paragraph: "MAIN-INLINE"
    rule_type: "guard"
    confidence: "high"
    reachable: true

validation:
  t01_schema_valid: null
  t02_structural_complete: null
  t02r_redefines_complete: null
  t03_functional_score: null
  t04_semantic_score: null
  t05_regression_pass: null
  overall: "PENDING"
---

# COBSWAIT — Utility Wait Program

## Purpose

COBSWAIT is a thin batch utility whose only responsibility is to pause the current job step for a caller-specified number of centiseconds. It acts as a wrapper around the z/OS `MVSWAIT` system service so that batch schedulers can insert timed delays between steps without writing assembler glue.

## Runtime Context

- Execution context: batch, z/OS.
- Invocation: one parameter passed on SYSIN — an 8-character digit string representing centiseconds.
- External services: one static CALL to the `MVSWAIT` load module.
- No file I/O, no VSAM access, no CICS services, no copybooks.

## Procedure Logic

The PROCEDURE DIVISION has no named paragraphs; it contains a single sequence of four statements represented here as the implicit `MAIN-INLINE` paragraph:

1. Accept an 8-byte character string `PARM-VALUE` from SYSIN.
2. Move `PARM-VALUE` into `MVSWAIT-TIME`, converting its character representation into the binary COMP integer required by MVSWAIT.
3. Call `MVSWAIT` passing `MVSWAIT-TIME` by reference — the operating system suspends execution for the indicated number of centiseconds.
4. Issue `STOP RUN` to terminate and return control to the job step dispatcher.

## Business Rules Surfaced

- **BR-001 (transform).** The caller-supplied parameter is reinterpreted from its character encoding on SYSIN into an 8-digit binary integer. The implicit contract is that the parameter must be numeric digits; non-numeric input will produce undefined MVSWAIT behaviour.
- **BR-002 (guard).** The program has no error handling — any failure reported by MVSWAIT is not inspected. The run completes successfully from the job-step point of view even if the wait itself was malformed.

## Graph Summary

- Program node: `COBSWAIT` / `Utility` / `Utility` / `Batch/VSAM`.
- One outbound CALL edge: `COBSWAIT → MVSWAIT` (STATIC).
- No copybook, VSAM, CICS, or business-rule edges beyond BR-001 and BR-002.
