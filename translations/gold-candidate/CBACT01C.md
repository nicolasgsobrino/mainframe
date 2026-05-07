---
schema_version: "cobol-md/1.0"
program_id: "CBACT01C"
source_file: "app/cbl/CBACT01C.cbl"
source_sha: "e680f8e4239a85eb9f95f129f282aa28e165496a"
translation_date: "2026-05-05"
translating_agent: "syncd-scaffold/1.1"
aifirst_task_id: "TODO-assign-task-id"
cfg_source: "validation/structure/CBACT01C_cfg.json"

business_domain: "TODO"
subtype: "TODO"  # Batch | Online | Utility

author: "AWS"
date_written: null
lines_of_code: 430
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

  - name: "FD-ACCTFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "OUT-ACCT-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "ARR-ARRAY-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "VBR-REC"
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

  - name: "OUTFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "ARRYFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "VBRCFILE-STATUS"
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

  - name: "END-OF-FILE"
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

  - name: "WS-RECD-LEN"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "VBRC-REC1"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "VBRC-REC2"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-ACCT-REISSUE-DATE"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-REISSUE-DATE"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"


procedure_paragraphs:

  - name: "0000-ACCTFILE-OPEN"
    reachable: true
    performs:


      - "2000-OUTFILE-OPEN"

      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "1000-ACCTFILE-GET-NEXT"
    reachable: true
    performs:


      - "1100-DISPLAY-ACCT-RECORD"

      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"

      - "1575-WRITE-VB2-RECORD"

      - "1550-WRITE-VB1-RECORD"

      - "1500-POPUL-VBRC-RECORD"

      - "1450-WRITE-ARRY-RECORD"

      - "1400-POPUL-ARRAY-RECORD"

      - "1350-WRITE-ACCT-RECORD"

      - "1300-POPUL-ACCT-RECORD"


    goto_targets:

      []

    summary: "TODO"

  - name: "1100-DISPLAY-ACCT-RECORD"
    reachable: true
    performs:


      - "1300-POPUL-ACCT-RECORD"


    goto_targets:

      []

    summary: "TODO"

  - name: "1300-POPUL-ACCT-RECORD"
    reachable: true
    performs:


      - "1350-WRITE-ACCT-RECORD"


    goto_targets:

      []

    summary: "TODO"

  - name: "1350-WRITE-ACCT-RECORD"
    reachable: true
    performs:


      - "1400-POPUL-ARRAY-RECORD"

      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "1400-POPUL-ARRAY-RECORD"
    reachable: true
    performs:


      - "1450-WRITE-ARRY-RECORD"


    goto_targets:

      []

    summary: "TODO"

  - name: "1450-WRITE-ARRY-RECORD"
    reachable: true
    performs:


      - "1500-POPUL-VBRC-RECORD"

      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "1500-POPUL-VBRC-RECORD"
    reachable: true
    performs:


      - "1550-WRITE-VB1-RECORD"


    goto_targets:

      []

    summary: "TODO"

  - name: "1550-WRITE-VB1-RECORD"
    reachable: true
    performs:


      - "1575-WRITE-VB2-RECORD"

      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "1575-WRITE-VB2-RECORD"
    reachable: true
    performs:


      - "0000-ACCTFILE-OPEN"

      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "2000-OUTFILE-OPEN"
    reachable: true
    performs:


      - "3000-ARRFILE-OPEN"

      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "3000-ARRFILE-OPEN"
    reachable: true
    performs:


      - "4000-VBRFILE-OPEN"

      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "4000-VBRFILE-OPEN"
    reachable: true
    performs:


      - "9000-ACCTFILE-CLOSE"

      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "9000-ACCTFILE-CLOSE"
    reachable: true
    performs:


      - "9999-ABEND-PROGRAM"

      - "9910-DISPLAY-IO-STATUS"


    goto_targets:

      []

    summary: "TODO"

  - name: "9910-DISPLAY-IO-STATUS"
    reachable: true
    performs:

      []

    goto_targets:

      []

    summary: "TODO"

  - name: "9999-ABEND-PROGRAM"
    reachable: true
    performs:


      - "9910-DISPLAY-IO-STATUS"


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
#   paragraphs_expected:     16
#   l01_items_expected:      21
#   reachable_expected:      16
#   dead_paragraphs_allowed: 0
#   goto_flag: False
#   alter_flag: False
translation_status: skeleton
translation_agent: pending
complexity_score: 16
risk_flags: []
bi_category: batch_cobol
last_audit: 2026-05-05
---


# CBACT01C -- TODO: short program description

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
