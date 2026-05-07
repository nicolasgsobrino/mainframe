---
schema_version: "cobol-md/1.0"
program_id: "CBSTM03A"
source_file: "app/cbl/CBSTM03A.CBL"
source_sha: "290c3f4a9c51e1f9aa5bb180237dfbeb1d02b26a"
translation_date: "2026-05-05"
translating_agent: "syncd-scaffold/1.1"
aifirst_task_id: "TODO-assign-task-id"
cfg_source: "validation/structure/CBSTM03A_cfg.json"

business_domain: "TODO"
subtype: "TODO"  # Batch | Online | Utility

author: "AWS"
date_written: null
lines_of_code: 924
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

  - name: "FD-STMTFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "FD-HTMLFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "COMP-VARIABLES"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "COMP3-VARIABLES"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "MISC-VARIABLES"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-M03B-AREA"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "STATEMENT-LINES"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "HTML-LINES"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-TRNX-TABLE"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-TRN-TBL-CNTR"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "PSAPTR"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "BUMP-TIOT"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "TIOT-INDEX"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "ALIGN-PSA"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "PSA-BLOCK"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "TCB-BLOCK"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "TIOT-BLOCK"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "TIOT-ENTRY"
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


      - "1000-MAINLINE"


    goto_targets:


      - "1000-MAINLINE"


    summary: "TODO"

  - name: "1000-MAINLINE"
    reachable: true
    performs:


      - "9999-GOBACK"

      - "9400-ACCTFILE-CLOSE"

      - "9300-CUSTFILE-CLOSE"

      - "9200-XREFFILE-CLOSE"

      - "9100-TRNXFILE-CLOSE"

      - "4000-TRNXFILE-GET"

      - "5000-CREATE-STATEMENT"

      - "3000-ACCTFILE-GET"

      - "2000-CUSTFILE-GET"

      - "1000-XREFFILE-GET-NEXT"


    goto_targets:

      []

    summary: "TODO"

  - name: "1000-XREFFILE-GET-NEXT"
    reachable: true
    performs:


      - "2000-CUSTFILE-GET"


    goto_targets:

      []

    summary: "TODO"

  - name: "2000-CUSTFILE-GET"
    reachable: true
    performs:


      - "3000-ACCTFILE-GET"


    goto_targets:

      []

    summary: "TODO"

  - name: "3000-ACCTFILE-GET"
    reachable: true
    performs:


      - "4000-TRNXFILE-GET"


    goto_targets:

      []

    summary: "TODO"

  - name: "4000-TRNXFILE-GET"
    reachable: true
    performs:


      - "5000-CREATE-STATEMENT"

      - "6000-WRITE-TRANS"


    goto_targets:

      []

    summary: "TODO"

  - name: "5000-CREATE-STATEMENT"
    reachable: true
    performs:


      - "5100-WRITE-HTML-HEADER"

      - "5200-WRITE-HTML-NMADBS"

      - "5200-EXIT"

      - "5100-EXIT"


    goto_targets:

      []

    summary: "TODO"

  - name: "5100-EXIT"
    reachable: true
    performs:


      - "5200-WRITE-HTML-NMADBS"


    goto_targets:

      []

    summary: "TODO"

  - name: "5100-WRITE-HTML-HEADER"
    reachable: true
    performs:


      - "5100-EXIT"


    goto_targets:

      []

    summary: "TODO"

  - name: "5200-EXIT"
    reachable: true
    performs:


      - "6000-WRITE-TRANS"


    goto_targets:

      []

    summary: "TODO"

  - name: "5200-WRITE-HTML-NMADBS"
    reachable: true
    performs:


      - "5200-EXIT"


    goto_targets:

      []

    summary: "TODO"

  - name: "6000-WRITE-TRANS"
    reachable: true
    performs:


      - "8100-FILE-OPEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "8100-FILE-OPEN"
    reachable: true
    performs:


      - "8100-TRNXFILE-OPEN"


    goto_targets:


      - "8100-TRNXFILE-OPEN"


    summary: "TODO"

  - name: "8100-TRNXFILE-OPEN"
    reachable: true
    performs:


      - "8200-XREFFILE-OPEN"

      - "0000-START"

      - "9999-ABEND-PROGRAM"


    goto_targets:


      - "0000-START"


    summary: "TODO"

  - name: "8200-XREFFILE-OPEN"
    reachable: true
    performs:


      - "8300-CUSTFILE-OPEN"

      - "0000-START"

      - "9999-ABEND-PROGRAM"


    goto_targets:


      - "0000-START"


    summary: "TODO"

  - name: "8300-CUSTFILE-OPEN"
    reachable: true
    performs:


      - "8400-ACCTFILE-OPEN"

      - "0000-START"

      - "9999-ABEND-PROGRAM"


    goto_targets:


      - "0000-START"


    summary: "TODO"

  - name: "8400-ACCTFILE-OPEN"
    reachable: true
    performs:


      - "8500-READTRNX-READ"

      - "1000-MAINLINE"

      - "9999-ABEND-PROGRAM"


    goto_targets:


      - "1000-MAINLINE"


    summary: "TODO"

  - name: "8500-READTRNX-READ"
    reachable: true
    performs:


      - "8599-EXIT"


    goto_targets:


      - "8599-EXIT"


    summary: "TODO"

  - name: "8599-EXIT"
    reachable: true
    performs:


      - "9100-TRNXFILE-CLOSE"

      - "0000-START"


    goto_targets:


      - "0000-START"


    summary: "TODO"

  - name: "9100-TRNXFILE-CLOSE"
    reachable: true
    performs:


      - "9200-XREFFILE-CLOSE"

      - "9999-ABEND-PROGRAM"


    goto_targets:

      []

    summary: "TODO"

  - name: "9200-XREFFILE-CLOSE"
    reachable: true
    performs:


      - "9300-CUSTFILE-CLOSE"

      - "9999-ABEND-PROGRAM"


    goto_targets:

      []

    summary: "TODO"

  - name: "9300-CUSTFILE-CLOSE"
    reachable: true
    performs:


      - "9400-ACCTFILE-CLOSE"

      - "9999-ABEND-PROGRAM"


    goto_targets:

      []

    summary: "TODO"

  - name: "9400-ACCTFILE-CLOSE"
    reachable: true
    performs:


      - "9999-ABEND-PROGRAM"


    goto_targets:

      []

    summary: "TODO"

  - name: "9999-ABEND-PROGRAM"
    reachable: true
    performs:

      []

    goto_targets:

      []

    summary: "TODO"

  - name: "9999-GOBACK"
    reachable: true
    performs:


      - "1000-XREFFILE-GET-NEXT"


    goto_targets:

      []

    summary: "TODO"



goto_acceptance:
  rationale: "TODO -- describe the GO TO pattern and why it is accepted"
  targets:



    - "1000-MAINLINE"



























    - "8100-TRNXFILE-OPEN"





    - "0000-START"





    - "0000-START"





    - "0000-START"





    - "1000-MAINLINE"





    - "8599-EXIT"





    - "0000-START"

















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
#   paragraphs_expected:     25
#   l01_items_expected:      18
#   reachable_expected:      25
#   dead_paragraphs_allowed: 0
#   goto_flag: True
#   alter_flag: True
translation_status: skeleton
translation_agent: pending
complexity_score: 65
risk_flags: ['goto_present']
bi_category: batch_report
last_audit: 2026-05-05
---


# CBSTM03A -- TODO: short program description

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
