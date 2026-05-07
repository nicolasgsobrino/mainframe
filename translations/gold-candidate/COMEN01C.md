---
schema_version: "cobol-md/1.0"
program_id: "COMEN01C"
source_file: "app/cbl/COMEN01C.cbl"
source_sha: "222db83b1ae9c01ef521342199d0234a4abd152d"
translation_date: "2026-05-05"
translating_agent: "syncd-scaffold/1.1"
aifirst_task_id: "TODO-assign-task-id"
cfg_source: "validation/structure/COMEN01C_cfg.json"

business_domain: "TODO"
subtype: "TODO"  # Batch | Online | Utility

author: "AWS"
date_written: null
lines_of_code: 308
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

  - name: "DFHCOMMAREA"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "TODO"


procedure_paragraphs:

  - name: "BUILD-MENU-OPTIONS"
    reachable: true
    performs:

      []

    goto_targets:

      []

    summary: "TODO"

  - name: "MAIN-PARA"
    reachable: true
    performs:


      - "PROCESS-ENTER-KEY"

      - "SEND-MENU-SCREEN"

      - "RECEIVE-MENU-SCREEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "POPULATE-HEADER-INFO"
    reachable: true
    performs:


      - "BUILD-MENU-OPTIONS"


    goto_targets:

      []

    summary: "TODO"

  - name: "PROCESS-ENTER-KEY"
    reachable: true
    performs:


      - "SEND-MENU-SCREEN"


    goto_targets:

      []

    summary: "TODO"

  - name: "RECEIVE-MENU-SCREEN"
    reachable: true
    performs:


      - "POPULATE-HEADER-INFO"


    goto_targets:

      []

    summary: "TODO"

  - name: "SEND-MENU-SCREEN"
    reachable: true
    performs:


      - "RECEIVE-MENU-SCREEN"

      - "BUILD-MENU-OPTIONS"

      - "POPULATE-HEADER-INFO"


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
#   paragraphs_expected:     6
#   l01_items_expected:      2
#   reachable_expected:      6
#   dead_paragraphs_allowed: 0
#   goto_flag: False
#   alter_flag: False
translation_status: skeleton
translation_agent: pending
complexity_score: 6
risk_flags: ['no_exit_paragraph']
bi_category: online_cobol
last_audit: 2026-05-05
---


# COMEN01C -- TODO: short program description

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
