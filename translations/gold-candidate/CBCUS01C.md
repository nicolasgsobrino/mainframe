---
schema_version: "cobol-md/1.0"
program_id: "CBCUS01C"
source_file: "app/cbl/CBCUS01C.cbl"
source_sha: "ad4c512be0d7bd72a933966d299ea21fb31b6b5b"
translation_date: "2026-05-06"
translating_agent: "syncd-scaffold/1.1"
aifirst_task_id: "TODO-assign-task-id"
cfg_source: "validation/structure/CBCUS01C_cfg.json"

business_domain: "TODO"
subtype: "TODO"  # Batch | Online | Utility

author: "AWS"
date_written: null
lines_of_code: 178
divisions:
  identification: true
  environment: true
  data: true
  procedure: true
environment:
  compiler: "IBM Enterprise COBOL"
  target: "TODO"  # Batch/VSAM | CICS/Online
  runtime: "z/OS"

calls_to: []  # TODO: fill from source
  # Each entry should have: program, condition, call_type
  # Example: - program: "MVSWAIT", condition: "unconditional", call_type: "STATIC"
called_by: []  # TODO: fill from source
copybooks_used: []  # TODO: fill from source

file_control: []  # TODO: fill from source

cics_commands: []
transaction_ids: []

data_items:

  - name: "FD-CUSTFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"

  - name: "CUSTFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"

  - name: "IO-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"

  - name: "TWO-BYTES-BINARY"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"

  - name: "TWO-BYTES-ALPHA"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"

  - name: "IO-STATUS-04"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"

  - name: "APPL-RESULT"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"

  - name: "END-OF-FILE"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"

  - name: "ABCODE"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"

  - name: "TIMING"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []  # TODO: fill when REDEFINES clause exists in source
      # Each entry should have: interpretation (semantic explanation of the redefined alias)
      # Example: "Redefined as packed decimal for monetary values"
    dead_code_flag: false
    semantic: "TODO"


procedure_paragraphs:

  - name: "0000-CUSTFILE-OPEN"
    reachable: true
    performs:


      - "9000-CUSTFILE-CLOSE"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "1000-CUSTFILE-GET-NEXT"
    reachable: true
    performs:


      - "0000-CUSTFILE-OPEN"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "9000-CUSTFILE-CLOSE"
    reachable: true
    performs:


      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "Z-ABEND-PROGRAM"
    reachable: true
    performs:


      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "Z-DISPLAY-IO-STATUS"
    reachable: true
    performs:

      []

    goto_targets:

      []

    summary: "TODO"




business_rules: []  # TODO: fill during translation
  # Each entry should have: id, rule, source_paragraph, rule_type, confidence, reachable
  # Example: - id: "BR-001", rule: "Wait duration must be positive", source_paragraph: "PERFORM-INIT", rule_type: "guard", confidence: "high", reachable: true

validation:
  t01_schema_valid: true
  t02_structural_complete: null
  t02r_redefines_complete: null
  t03_functional_score: null
  t04_semantic_score: null
  t05_regression_pass: null
  overall: "PENDING"

# Locked numbers (from SYNC-MANIFEST.yaml):
#   paragraphs_expected:     5
#   l01_items_expected:      10
#   reachable_expected:      5
#   dead_paragraphs_allowed: 0
#   goto_flag: False
#   alter_flag: False
---

# CBCUS01C -- TODO: short program description

## Purpose

TODO: Describe what this program does and its business function.

## Data Layout

TODO: Describe the key data structures.

## Control Flow

TODO: Describe paragraph-level logic in plain English.

## GO TO Suppression Rationale


No GO TO statements detected in CFG.


## Translation Targets

TODO: List key COBOL constructs and their target-language equivalents.
