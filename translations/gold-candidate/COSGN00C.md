---
schema_version: "cobol-md/1.0"
program_id: "COSGN00C"
source_file: "app/cbl/COSGN00C.cbl"
source_sha: "28e2061e3f0ec1fbde590b0cf2236e2919567aee"
translation_date: "2026-05-05"
translating_agent: "syncd-scaffold/1.1"
aifirst_task_id: "TODO-assign-task-id"
cfg_source: "validation/structure/COSGN00C_cfg.json"

business_domain: "TODO"
subtype: "TODO"  # Batch | Online | Utility

author: "AWS"
date_written: null
lines_of_code: 260
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

  - name: "WS-VARIABLES"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-PGMNAME"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-TRANID"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-MESSAGE"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-USRSEC-FILE"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-ERR-FLG"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "ERR-FLG-ON"
    level: 88
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "ERR-FLG-OFF"
    level: 88
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-RESP-CD"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-REAS-CD"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-USER-ID"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "WS-USER-PWD"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "DFHCOMMAREA"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"

  - name: "LK-COMMAREA"
    level: 5
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"


procedure_paragraphs:

  - name: "MAIN-PARA"
    reachable: true
    performs:


      - "SEND-SIGNON-SCREEN"

      - "PROCESS-ENTER-KEY"

      - "SEND-PLAIN-TEXT"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "READ-USER-SEC-FILE"

      - "POPULATE-HEADER-INFO"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "END-IF"
    reachable: false
    performs:


      - "SEND-SIGNON-SCREEN"

      - "PROCESS-ENTER-KEY"

      - "SEND-PLAIN-TEXT"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "READ-USER-SEC-FILE"

      - "POPULATE-HEADER-INFO"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "END-EXEC"
    reachable: false
    performs:


      - "SEND-SIGNON-SCREEN"

      - "PROCESS-ENTER-KEY"

      - "SEND-PLAIN-TEXT"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "READ-USER-SEC-FILE"

      - "POPULATE-HEADER-INFO"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "PROCESS-ENTER-KEY"
    reachable: true
    performs:


      - "SEND-SIGNON-SCREEN"

      - "SEND-PLAIN-TEXT"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "READ-USER-SEC-FILE"

      - "POPULATE-HEADER-INFO"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "END-EVALUATE"
    reachable: false
    performs:


      - "SEND-SIGNON-SCREEN"

      - "PROCESS-ENTER-KEY"

      - "SEND-PLAIN-TEXT"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "READ-USER-SEC-FILE"

      - "POPULATE-HEADER-INFO"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "SEND-SIGNON-SCREEN"
    reachable: true
    performs:


      - "PROCESS-ENTER-KEY"

      - "SEND-PLAIN-TEXT"

      - "READ-USER-SEC-FILE"

      - "POPULATE-HEADER-INFO"


    goto_targets:

      []

    summary: "TODO"

  - name: "SEND-PLAIN-TEXT"
    reachable: true
    performs:


      - "SEND-SIGNON-SCREEN"

      - "PROCESS-ENTER-KEY"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "READ-USER-SEC-FILE"

      - "POPULATE-HEADER-INFO"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "POPULATE-HEADER-INFO"
    reachable: true
    performs:


      - "SEND-SIGNON-SCREEN"

      - "PROCESS-ENTER-KEY"

      - "SEND-PLAIN-TEXT"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "READ-USER-SEC-FILE"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "READ-USER-SEC-FILE"
    reachable: true
    performs:


      - "SEND-SIGNON-SCREEN"

      - "PROCESS-ENTER-KEY"

      - "SEND-PLAIN-TEXT"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "POPULATE-HEADER-INFO"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"

      - "SEND-SIGNON-SCREEN"


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
#   paragraphs_expected:     9
#   l01_items_expected:      14
#   reachable_expected:      6
#   dead_paragraphs_allowed: 3
#   goto_flag: False
#   alter_flag: False
translation_status: skeleton
translation_agent: pending
complexity_score: 9
risk_flags: ['no_exit_paragraph']
bi_category: online_cobol
last_audit: 2026-05-05
---


# COSGN00C -- TODO: short program description

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
