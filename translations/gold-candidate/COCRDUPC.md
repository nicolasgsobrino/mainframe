---
schema_version: "cobol-md/1.0"
program_id: "COCRDUPC"
source_file: "app/cbl/COCRDUPC.cbl"
source_sha: "10f06557a9e332711bf2e077a821ad6c4bc3c532"
translation_date: "2026-05-05"
translating_agent: "syncd-scaffold/1.1"
aifirst_task_id: "TODO-assign-task-id"
cfg_source: "validation/structure/COCRDUPC_cfg.json"

business_domain: "TODO"
subtype: "TODO"  # Batch | Online | Utility

author: "AWS"
date_written: null
lines_of_code: 402
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


procedure_paragraphs:




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
#   paragraphs_expected:     0
#   l01_items_expected:      0
#   reachable_expected:      0
#   dead_paragraphs_allowed: 0
#   goto_flag: False
#   alter_flag: False
translation_status: skeleton
translation_agent: pending
complexity_score: 0
risk_flags: ['no_exit_paragraph']
bi_category: online_cobol
last_audit: 2026-05-05
---


# COCRDUPC -- TODO: short program description

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
