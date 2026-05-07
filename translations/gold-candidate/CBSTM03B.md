---
schema_version: "cobol-md/1.0"
program_id: "CBSTM03B"
source_file: "app/cbl/CBSTM03B.CBL"
source_sha: "7d70690ea9afada3c21f227c0a1f9602af39c89d"
translation_date: "2026-05-05"
translating_agent: "syncd-scaffold/1.1"
aifirst_task_id: "TODO-assign-task-id"
cfg_source: "validation/structure/CBSTM03B_cfg.json"

business_domain: "TODO"
subtype: "TODO"  # Batch | Online | Utility

author: "AWS"
date_written: null
lines_of_code: 230
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
called_by: []  # TODO: fill from source
copybooks_used: []  # TODO: fill from source

file_control: []  # TODO: fill from source

cics_commands: []
transaction_ids: []

data_items:

  - name: "FD-TRNXFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "FD-XREFFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "FD-CUSTFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "FD-ACCTFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "TRNXFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "XREFFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "CUSTFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "ACCTFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "LK-M03B-AREA"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"


procedure_paragraphs:

  - name: "0000-START"
    reachable: true
    performs:


      - "9999-GOBACK"


    goto_targets:


      - "9999-GOBACK"


    summary: "TODO"

  - name: "1000-TRNXFILE-PROC"
    reachable: true
    performs:


      - "1900-EXIT"


    goto_targets:


      - "1900-EXIT"


    summary: "TODO"

  - name: "1900-EXIT"
    reachable: true
    performs:


      - "1999-EXIT"


    goto_targets:

      []

    summary: "TODO"

  - name: "1999-EXIT"
    reachable: true
    performs:


      - "2000-XREFFILE-PROC"


    goto_targets:

      []

    summary: "TODO"

  - name: "2000-XREFFILE-PROC"
    reachable: true
    performs:


      - "2900-EXIT"


    goto_targets:


      - "2900-EXIT"


    summary: "TODO"

  - name: "2900-EXIT"
    reachable: true
    performs:


      - "2999-EXIT"


    goto_targets:

      []

    summary: "TODO"

  - name: "2999-EXIT"
    reachable: true
    performs:


      - "3000-CUSTFILE-PROC"


    goto_targets:

      []

    summary: "TODO"

  - name: "3000-CUSTFILE-PROC"
    reachable: true
    performs:


      - "3900-EXIT"


    goto_targets:


      - "3900-EXIT"


    summary: "TODO"

  - name: "3900-EXIT"
    reachable: true
    performs:


      - "3999-EXIT"


    goto_targets:

      []

    summary: "TODO"

  - name: "3999-EXIT"
    reachable: true
    performs:


      - "4000-ACCTFILE-PROC"


    goto_targets:

      []

    summary: "TODO"

  - name: "4000-ACCTFILE-PROC"
    reachable: true
    performs:


      - "4900-EXIT"


    goto_targets:


      - "4900-EXIT"


    summary: "TODO"

  - name: "4900-EXIT"
    reachable: true
    performs:


      - "4999-EXIT"


    goto_targets:

      []

    summary: "TODO"

  - name: "4999-EXIT"
    reachable: true
    performs:

      []

    goto_targets:

      []

    summary: "TODO"

  - name: "9999-GOBACK"
    reachable: true
    performs:


      - "1000-TRNXFILE-PROC"


    goto_targets:

      []

    summary: "TODO"



goto_acceptance:
  rationale: "TODO -- describe the GO TO pattern and why it is accepted"
  targets:



    - "9999-GOBACK"





    - "1900-EXIT"









    - "2900-EXIT"









    - "3900-EXIT"









    - "4900-EXIT"











business_rules: []  # TODO: fill during translation

validation:
  t01_schema_valid: true
  t02_structural_complete: null
  t02r_redefines_complete: null
  t03_functional_score: null
  t04_semantic_score: null
  t05_regression_pass: null
  overall: "PENDING"

# Locked numbers (from SYNC-MANIFEST.yaml):
#   paragraphs_expected:     14
#   l01_items_expected:      9
#   reachable_expected:      14
#   dead_paragraphs_allowed: 0
#   goto_flag: True
#   alter_flag: True
translation_status: skeleton
translation_agent: pending
complexity_score: 39
risk_flags: ['goto_present']
bi_category: batch_report
last_audit: 2026-05-05
---


# CBSTM03B -- TODO: short program description

## Purpose

TODO: Describe what this program does and its business function.

## Data Layout

TODO: Describe the key data structures.

## Control Flow

TODO: Describe paragraph-level logic in plain English.

## GO TO Suppression Rationale


TODO: Explain the GO TO pattern and justify acceptance under Cobol-REKT RC8.


## Translation Targets

TODO: List key COBOL constructs and their target-language equivalents.
