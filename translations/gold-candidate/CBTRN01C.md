---
schema_version: "cobol-md/1.0"
program_id: "CBTRN01C"
source_file: "app/cbl/CBTRN01C.cbl"
source_sha: "450bd63983e78e1cca8719e72cbdf7cfccfb9630"
translation_date: "2026-05-05"
translating_agent: "syncd-scaffold/1.1"
aifirst_task_id: "TODO-assign-task-id"
cfg_source: "validation/structure/CBTRN01C_cfg.json"

business_domain: "TODO"
subtype: "TODO"  # Batch | Online | Utility

author: "AWS"
date_written: null
lines_of_code: 494
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

  - name: "FD-TRAN-RECORD"
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

  - name: "FD-XREFFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "FD-CARDFILE-REC"
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

  - name: "FD-TRANFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "DALYTRAN-STATUS"
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

  - name: "XREFFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "CARDFILE-STATUS"
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

  - name: "TRANFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "IO-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "TWO-BYTES-BINARY"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "TWO-BYTES-ALPHA"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "IO-STATUS-04"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "APPL-RESULT"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "END-OF-DAILY-TRANS-FILE"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "ABCODE"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "TIMING"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-MISC-VARIABLES"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"


procedure_paragraphs:

  - name: "0000-DALYTRAN-OPEN"
    reachable: true
    performs:


      - "0100-CUSTFILE-OPEN"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "0100-CUSTFILE-OPEN"
    reachable: true
    performs:


      - "0200-XREFFILE-OPEN"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "0200-XREFFILE-OPEN"
    reachable: true
    performs:


      - "0300-CARDFILE-OPEN"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "0300-CARDFILE-OPEN"
    reachable: true
    performs:


      - "0400-ACCTFILE-OPEN"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "0400-ACCTFILE-OPEN"
    reachable: true
    performs:


      - "0500-TRANFILE-OPEN"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "0500-TRANFILE-OPEN"
    reachable: true
    performs:


      - "9000-DALYTRAN-CLOSE"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "1000-DALYTRAN-GET-NEXT"
    reachable: true
    performs:


      - "2000-LOOKUP-XREF"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "2000-LOOKUP-XREF"
    reachable: true
    performs:


      - "3000-READ-ACCOUNT"


    goto_targets:

      []

    summary: "TODO"

  - name: "3000-READ-ACCOUNT"
    reachable: true
    performs:


      - "0000-DALYTRAN-OPEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "9000-DALYTRAN-CLOSE"
    reachable: true
    performs:


      - "9100-CUSTFILE-CLOSE"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "9100-CUSTFILE-CLOSE"
    reachable: true
    performs:


      - "9200-XREFFILE-CLOSE"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "9200-XREFFILE-CLOSE"
    reachable: true
    performs:


      - "9300-CARDFILE-CLOSE"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "9300-CARDFILE-CLOSE"
    reachable: true
    performs:


      - "9400-ACCTFILE-CLOSE"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "9400-ACCTFILE-CLOSE"
    reachable: true
    performs:


      - "9500-TRANFILE-CLOSE"

      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "9500-TRANFILE-CLOSE"
    reachable: true
    performs:


      - "Z-ABEND-PROGRAM"

      - "Z-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "MAIN-PARA"
    reachable: true
    performs:


      - "1000-DALYTRAN-GET-NEXT"

      - "9500-TRANFILE-CLOSE"

      - "9400-ACCTFILE-CLOSE"

      - "9300-CARDFILE-CLOSE"

      - "9200-XREFFILE-CLOSE"

      - "9100-CUSTFILE-CLOSE"

      - "9000-DALYTRAN-CLOSE"

      - "3000-READ-ACCOUNT"

      - "2000-LOOKUP-XREF"

      - "0500-TRANFILE-OPEN"

      - "0400-ACCTFILE-OPEN"

      - "0300-CARDFILE-OPEN"

      - "0200-XREFFILE-OPEN"

      - "0100-CUSTFILE-OPEN"

      - "0000-DALYTRAN-OPEN"


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

validation:
  t01_schema_valid: true
  t02_structural_complete: null
  t02r_redefines_complete: null
  t03_functional_score: null
  t04_semantic_score: null
  t05_regression_pass: null
  overall: "PENDING"

# Locked numbers (from SYNC-MANIFEST.yaml):
#   paragraphs_expected:     18
#   l01_items_expected:      21
#   reachable_expected:      18
#   dead_paragraphs_allowed: 0
#   goto_flag: False
#   alter_flag: False
translation_status: skeleton
translation_agent: pending
complexity_score: 18
risk_flags: ['no_exit_paragraph']
bi_category: batch_cobol
last_audit: 2026-05-05
---


# CBTRN01C -- TODO: short program description

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
