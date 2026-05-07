---
schema_version: "cobol-md/1.0"
program_id: "CBACT04C"
source_file: "app/cbl/CBACT04C.cbl"
source_sha: "c5e0280e2ed0891877b43eda7bc7c6dc86752421"
translation_date: "2026-05-06"
translating_agent: "qwen3-coder-next-80b"
aifirst_task_id: "T-2026-05-06-001"
cfg_source: "validation/structure/CBACT04C_cfg.json"

business_domain: "Financial Services"
subtype: "Batch"  # Batch | Online | Utility

author: "AWS"
date_written: null
lines_of_code: 652
divisions:
  identification: true
  environment: true
  data: true
  procedure: true
environment:
  compiler: "IBM Enterprise COBOL"
  target: "Batch/VSAM"  # Batch/VSAM | CICS/Online
  runtime: "z/OS"

calls_to:
  - program: "CEE3ABD"
    condition: "unconditional"
    call_type: "STATIC"
called_by: []
copybooks_used:
  - "CVTRA01Y"
  - "CVACT03Y"
  - "CVTRA02Y"
  - "CVACT01Y"
  - "CVTRA05Y"

file_control:
  - file_name: "TCATBAL-FILE"
    assign_to: "TCATBALF"
    organization: "INDEXED"
    access_mode: "SEQUENTIAL"
    record_key: "FD-TRAN-CAT-KEY"
    file_status: "TCATBALF-STATUS"
  - file_name: "XREF-FILE"
    assign_to: "XREFFILE"
    organization: "INDEXED"
    access_mode: "RANDOM"
    record_key: "FD-XREF-CARD-NUM"
    alternate_record_key: "FD-XREF-ACCT-ID"
    file_status: "XREFFILE-STATUS"
  - file_name: "ACCOUNT-FILE"
    assign_to: "ACCTFILE"
    organization: "INDEXED"
    access_mode: "RANDOM"
    record_key: "FD-ACCT-ID"
    file_status: "ACCTFILE-STATUS"
  - file_name: "DISCGRP-FILE"
    assign_to: "DISCGRP"
    organization: "INDEXED"
    access_mode: "RANDOM"
    record_key: "FD-DISCGRP-KEY"
    file_status: "DISCGRP-STATUS"
  - file_name: "TRANSACT-FILE"
    assign_to: "TRANSACT"
    organization: "SEQUENTIAL"
    access_mode: "SEQUENTIAL"
    file_status: "TRANFILE-STATUS"

cics_commands: []
transaction_ids: []

data_items:

  - name: "FD-TRAN-CAT-BAL-RECORD"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Transaction Category Balance file record containing account ID, transaction type, transaction code, and data fields"

  - name: "FD-XREFFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Cross-reference file record mapping card numbers to account IDs"

  - name: "FD-DISCGRP-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Disclosure group file record containing interest rate information"

  - name: "FD-ACCTFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Account master file record containing account balance and activity data"

  - name: "FD-TRANFILE-REC"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Transaction file output record for interest posted transactions"

  - name: "TCATBALF-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "File status indicator for transaction category balance file operations"

  - name: "XREFFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "File status indicator for cross-reference file operations"

  - name: "DISCGRP-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "File status indicator for disclosure group file operations"

  - name: "ACCTFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "File status indicator for account master file operations"

  - name: "TRANFILE-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "File status indicator for transaction file operations"

  - name: "IO-STATUS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "I/O status indicator for display purposes"

  - name: "TWO-BYTES-BINARY"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-byte binary field for numeric operations"

  - name: "TWO-BYTES-ALPHA"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: "TWO-BYTES-BINARY"
    redefines_interpretations:
      - interpretation: "Redefined as two single-byte alphanumeric fields for character operations"
    dead_code_flag: false
    semantic: "Two-byte alpha field (REDEFINES TWO-BYTES-BINARY) for character operations"

  - name: "IO-STATUS-04"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Four-byte field for formatted I/O status display"

  - name: "APPL-RESULT"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Application result code (binary format) for error handling"

  - name: "END-OF-FILE"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "End-of-file indicator flag ('Y' or 'N')"

  - name: "ABCODE"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Abend code for program termination"

  - name: "TIMING"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Timing parameter for abend calls"

  - name: "COBOL-TS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "COBOL current date/time timestamp structure"

  - name: "DB2-FORMAT-TS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "DB2 timestamp format (26-character string)"

  - name: "FILLER"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: "DB2-FORMAT-TS"
    redefines_interpretations:
      - interpretation: "Redefined as DB2 timestamp components for individual date/time element access"
    dead_code_flag: false
    semantic: "Filler field (REDEFINES DB2-FORMAT-TS) for DB2 timestamp component access"

  - name: "WS-MISC-VARS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Working storage miscellaneous variables including last account number, monthly interest, total interest, and first-time flag"

  - name: "WS-COUNTERS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Working storage counters including record count and transaction ID suffix"

  - name: "EXTERNAL-PARMS"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Linkage section external parameters including parameter length and date"

procedure_paragraphs:

  - name: "0000-TCATBALF-OPEN"
    reachable: true
    performs:
      - "0100-XREFFILE-OPEN"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Open transaction category balance file for input, set application result code, handle errors by displaying file status and abending"

  - name: "0100-XREFFILE-OPEN"
    reachable: true
    performs:
      - "0200-DISCGRP-OPEN"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Open cross-reference file for input, set application result code, handle errors by displaying file status and abending"

  - name: "0200-DISCGRP-OPEN"
    reachable: true
    performs:
      - "0300-ACCTFILE-OPEN"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Open disclosure group file for input, set application result code, handle errors by displaying file status and abending"

  - name: "0300-ACCTFILE-OPEN"
    reachable: true
    performs:
      - "0400-TRANFILE-OPEN"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Open account master file for I-O (read/write), set application result code, handle errors by displaying file status and abending"

  - name: "0400-TRANFILE-OPEN"
    reachable: true
    performs:
      - "1000-TCATBALF-GET-NEXT"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Open transaction file for output, then begin processing loop by reading next transaction category balance record"

  - name: "1000-TCATBALF-GET-NEXT"
    reachable: true
    performs:
      - "1050-UPDATE-ACCOUNT"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Read next transaction category balance record, check for end-of-file (status 10), handle read errors by displaying status and abending"

  - name: "1050-UPDATE-ACCOUNT"
    reachable: true
    performs:
      - "1100-GET-ACCT-DATA"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Update account record balances by adding total interest, resetting cycle credit/debit to zero, then rewriting account file record"

  - name: "1100-GET-ACCT-DATA"
    reachable: true
    performs:
      - "1110-GET-XREF-DATA"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Read account master file record by account ID, handle invalid key by displaying error message, check file status for read errors"

  - name: "1110-GET-XREF-DATA"
    reachable: true
    performs:
      - "1200-GET-INTEREST-RATE"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Read cross-reference file record by account ID key, handle invalid key by displaying error message, check file status for read errors"

  - name: "1200-A-GET-DEFAULT-INT-RATE"
    reachable: true
    performs:
      - "1300-COMPUTE-INTEREST"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Read disclosure group file with default group code to get default interest rate, handle errors by displaying status and abending"

  - name: "1200-GET-INTEREST-RATE"
    reachable: true
    performs:
      - "1200-A-GET-DEFAULT-INT-RATE"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Read disclosure group file record by account group ID and transaction type/category codes; if record not found (status 23), use default group code"

  - name: "1300-B-WRITE-TX"
    reachable: true
    performs:
      - "1400-COMPUTE-FEES"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
      - "Z-GET-DB2-FORMAT-TIMESTAMP"
    goto_targets: []
    summary: "Generate transaction ID from date and suffix, populate transaction record with interest data and DB2 timestamps, write to transaction file"

  - name: "1300-COMPUTE-INTEREST"
    reachable: true
    performs:
      - "1300-B-WRITE-TX"
    goto_targets: []
    summary: "Compute monthly interest using formula (TRAN-CAT-BAL * DIS-INT-RATE) / 1200, add to total interest, then write transaction record"

  - name: "1400-COMPUTE-FEES"
    reachable: true
    performs:
      - "9000-TCATBALF-CLOSE"
    goto_targets: []
    summary: "Fee computation placeholder - to be implemented (currently no-op exit)"

  - name: "9000-TCATBALF-CLOSE"
    reachable: true
    performs:
      - "9100-XREFFILE-CLOSE"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Close transaction category balance file, handle close errors by displaying status and abending"

  - name: "9100-XREFFILE-CLOSE"
    reachable: true
    performs:
      - "9200-DISCGRP-CLOSE"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Close cross-reference file, handle close errors by displaying status and abending"

  - name: "9200-DISCGRP-CLOSE"
    reachable: true
    performs:
      - "9300-ACCTFILE-CLOSE"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Close disclosure group file, handle close errors by displaying status and abending"

  - name: "9300-ACCTFILE-CLOSE"
    reachable: true
    performs:
      - "9400-TRANFILE-CLOSE"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Close account master file, handle close errors by displaying status and abending"

  - name: "9400-TRANFILE-CLOSE"
    reachable: true
    performs:
      - "Z-GET-DB2-FORMAT-TIMESTAMP"
      - "9999-ABEND-PROGRAM"
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Close transaction file, generate DB2 timestamp for final processing, handle close errors by displaying status and abending"

  - name: "9910-DISPLAY-IO-STATUS"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Display formatted I/O status - converts numeric or alphanumeric status to displayable NNNN format with actual status code"

  - name: "9999-ABEND-PROGRAM"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Abend program by calling CEE3ABD with abend code 999 and timing zero"

  - name: "Z-GET-DB2-FORMAT-TIMESTAMP"
    reachable: true
    performs:
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Convert COBOL current date to DB2 timestamp format (YYYY-MM-DD-HH.MM.SS.MILLL000) for transaction timestamp fields"

business_rules:
  - id: "BR-001"
    rule: "Account group ID, transaction type code, and transaction category code must uniquely identify a disclosure group record"
    source_paragraph: "1200-GET-INTEREST-RATE"
    rule_type: "guard"
    confidence: "high"
    reachable: true
  - id: "BR-002"
    rule: "If disclosure group record not found, use default group code 'DEFAULT' to retrieve interest rate"
    source_paragraph: "1200-GET-INTEREST-RATE"
    rule_type: "transform"
    confidence: "high"
    reachable: true
  - id: "BR-003"
    rule: "Monthly interest is calculated as (transaction category balance * interest rate) / 1200"
    source_paragraph: "1300-COMPUTE-INTEREST"
    rule_type: "calculation"
    confidence: "high"
    reachable: true
  - id: "BR-004"
    rule: "Account balances are updated by adding total accumulated monthly interest to current balance"
    source_paragraph: "1050-UPDATE-ACCOUNT"
    rule_type: "transform"
    confidence: "high"
    reachable: true
  - id: "BR-005"
    rule: "Transaction records include DB2 format timestamps for both original and processing timestamps"
    source_paragraph: "1300-B-WRITE-TX"
    rule_type: "io"
    confidence: "high"
    reachable: true

validation:
  t01_schema_valid: true
  t02_structural_complete: null
  t02r_redefines_complete: null
  t03_functional_score: null
  t04_semantic_score: null
  t05_regression_pass: null
  overall: "PENDING"

# Locked numbers (from SYNC-MANIFEST.yaml):
#   paragraphs_expected:     22
#   l01_items_expected:      24
#   reachable_expected:      22
#   dead_paragraphs_allowed: 0
#   goto_flag: False
#   alter_flag: False
---

# CBACT04C -- Batch Interest Calculator Program

## Purpose

CBACT04C is a batch processing program that calculates interest for customer accounts. The program reads transaction category balance records, retrieves account and cross-reference data, calculates interest based on disclosure group rates, and posts interest transactions to the transaction file. It processes records in sequential order, updating account balances and generating interest transaction records for each account.

## Data Layout

### File Section Records

- **FD-TRAN-CAT-BAL-RECORD**: Transaction category balance file record (39 bytes) containing account ID (11 digits), transaction type code (2 chars), transaction category code (4 digits), and data field (33 chars)

- **FD-XREFFILE-REC**: Cross-reference file record (54 bytes) mapping card numbers to account IDs with customer number and filler fields

- **FD-DISCGRP-REC**: Disclosure group file record (48 bytes) containing account group ID, transaction type/category codes, and data field with interest rates

- **FD-ACCTFILE-REC**: Account master file record (300 bytes) containing account ID and account data with balance information

- **FD-TRANFILE-REC**: Transaction output file record (350 bytes) containing transaction ID, account data, and transaction details

### Working Storage Variables

- **Status Fields**: File status indicators for each file (TCATBALF-STATUS, XREFFILE-STATUS, DISCGRP-STATUS, ACCTFILE-STATUS, TRANFILE-STATUS, IO-STATUS)
- **Application Result**: APPL-RESULT (binary) for error handling with 88-level conditions APPL-AOK (0) and APPL-EOF (16)
- **End-of-File**: END-OF-FILE flag ('Y' or 'N')
- **Binary Fields**: TWO-BYTES-BINARY (PIC 9(4) BINARY), TWO-BYTES-ALPHA (REDEFINES)
- **Timestamp**: COBOL-TS structure converted to DB2-FORMAT-TS (26-char string)
- **Interest Variables**: WS-MONTHLY-INT, WS-TOTAL-INT (scaled decimal), WS-FIRST-TIME flag
- **Counters**: WS-RECORD-COUNT, WS-TRANID-SUFFIX

## Control Flow

The program follows a structured flow with no GO TO statements:

1. **Initialization (Lines 182-186)**: Open all files in sequence - transaction category balance, cross-reference, disclosure group, account master, and transaction files

2. **Main Processing Loop (Lines 188-222)**: 
   - Read next transaction category balance record
   - If not end-of-file:
     - Check if new account (compare with last account number)
     - If new account, update previous account balance and reset counters
     - Read account master and cross-reference data
     - Get interest rate from disclosure group
     - If rate > 0, compute interest and fees
   - If end-of-file, perform final account update

3. **Per-Account Processing**:
   - Update account record with accumulated interest
   - Reset cycle credit/debit to zero
   - Rewrite account file

4. **Interest Calculation**:
   - Read disclosure group by account group ID and transaction codes
   - If not found (status 23), use default group code
   - Compute monthly interest: (balance * rate) / 1200
   - Add to total interest for account

5. **Transaction Generation**:
   - Generate transaction ID from date + suffix
   - Populate transaction record with interest data
   - Write to transaction file

6. **Cleanup (Lines 224-228)**: Close all files in reverse order

7. **Termination (Line 232)**: GOBACK to caller

## GO TO Suppression Rationale

No GO TO statements detected in CFG. The program uses structured COBOL constructs including PERFORM loops, END-IF, and END-PERFORM for all control flow. Error handling is implemented through sequential PERFORM calls to abend and status display routines.

## Translation Targets

| COBOL Construct | Translation Target |
|---|---|
| PERFORM loop | while loop with condition |
| PERFORM UNTIL | do-while loop |
| END-IF | closing brace for if block |
| END-PERFORM | closing brace for perform block |
| MOVE | assignment statement |
| ADD | arithmetic assignment |
| READ | file read operation |

## References

- COBOL Source: `app/cbl/CBACT04C.cbl` (652 lines)
- CFG Source: `validation/structure/CBACT04C_cfg.json`
- Task ID: `T-2026-05-06-001`