---
# ── Identity ───────────────────────────────────────────────────────────────────
schema_version: "cobol-md/1.0"
program_id: "CBTRN01C"
source_file: "app/cbl/CBTRN01C.cbl"
source_sha: "6494be3b695bd33f27b39f8d13dc5b510f92b7ed"
translation_date: "2026-04-23"
translating_agent: "claude-opus-4-5 (subagent)"
aifirst_task_id: "T-2026-04-23-001"
cfg_source: "validation/structure/CBTRN01C_cfg.json"

# ── Classification ─────────────────────────────────────────────────────────────
business_domain: "Transaction Processing"
subtype: "Batch"

# ── Structural Metadata ────────────────────────────────────────────────────────
author: "AWS"
date_written: null
lines_of_code: 340
divisions:
  identification: true
  environment: true
  data: true
  procedure: true
environment:
  compiler: "IBM Enterprise COBOL"
  target: "Batch/VSAM"
  runtime: "z/OS"

# ── Graph Edges ────────────────────────────────────────────────────────────────
calls_to:
  - program: "CEE3ABD"
    condition: "Unrecoverable I/O error detected on any file open, read, or close operation"
    call_type: "STATIC"

called_by: []

copybooks_used:
  - name: "CVTRA06Y"
    path: "app/cpy/CVTRA06Y.cpy"
    sha: null
  - name: "CVCUS01Y"
    path: "app/cpy/CVCUS01Y.cpy"
    sha: null
  - name: "CVACT03Y"
    path: "app/cpy/CVACT03Y.cpy"
    sha: null
  - name: "CVACT02Y"
    path: "app/cpy/CVACT02Y.cpy"
    sha: null
  - name: "CVACT01Y"
    path: "app/cpy/CVACT01Y.cpy"
    sha: null
  - name: "CVTRA05Y"
    path: "app/cpy/CVTRA05Y.cpy"
    sha: null

# ── File I/O ───────────────────────────────────────────────────────────────────
file_control:
  - ddname: "DALYTRAN"
    organization: "SEQUENTIAL"
    access: "SEQUENTIAL"
    record_key: null
    crud: ["READ"]
  - ddname: "CUSTFILE"
    organization: "INDEXED"
    access: "RANDOM"
    record_key: "FD-CUST-ID"
    crud: ["READ"]
  - ddname: "XREFFILE"
    organization: "INDEXED"
    access: "RANDOM"
    record_key: "FD-XREF-CARD-NUM"
    crud: ["READ"]
  - ddname: "CARDFILE"
    organization: "INDEXED"
    access: "RANDOM"
    record_key: "FD-CARD-NUM"
    crud: ["READ"]
  - ddname: "ACCTFILE"
    organization: "INDEXED"
    access: "RANDOM"
    record_key: "FD-ACCT-ID"
    crud: ["READ"]
  - ddname: "TRANFILE"
    organization: "INDEXED"
    access: "RANDOM"
    record_key: "FD-TRANS-ID"
    crud: ["READ"]

# ── CICS ───────────────────────────────────────────────────────────────────────
cics_commands: []
transaction_ids: []

# ── Data Layer ─────────────────────────────────────────────────────────────────
data_items:
  # File Section — DALYTRAN-FILE (daily transaction sequential input)
  - name: "FD-TRAN-RECORD"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Root record layout for the daily transaction sequential input file; contains a 16-character transaction identifier followed by 334 bytes of payload data"

  # File Section — CUSTOMER-FILE (customer VSAM indexed)
  - name: "FD-CUSTFILE-REC"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Root record layout for the customer VSAM indexed file; primary key is a 9-digit numeric customer identifier"

  # File Section — XREF-FILE (card cross-reference VSAM indexed)
  - name: "FD-XREFFILE-REC"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Root record layout for the card-to-account cross-reference VSAM indexed file; primary key is the 16-character card number"

  # File Section — CARD-FILE (card VSAM indexed)
  - name: "FD-CARDFILE-REC"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Root record layout for the card detail VSAM indexed file; primary key is the 16-character card number"

  # File Section — ACCOUNT-FILE (account VSAM indexed)
  - name: "FD-ACCTFILE-REC"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Root record layout for the account VSAM indexed file; primary key is an 11-digit numeric account identifier"

  # File Section — TRANSACT-FILE (transaction VSAM indexed)
  - name: "FD-TRANFILE-REC"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Root record layout for the posted-transaction VSAM indexed file; primary key is a 16-character transaction identifier"

  # Working Storage — file status areas
  - name: "DALYTRAN-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file status code returned by the operating system after each I/O operation on the daily transaction sequential file"

  - name: "CUSTFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file status code for the customer VSAM indexed file; populated after every open, read, and close"

  - name: "XREFFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file status code for the card cross-reference VSAM indexed file; used to detect invalid-key conditions during random reads"

  - name: "CARDFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file status code for the card detail VSAM indexed file"

  - name: "ACCTFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file status code for the account VSAM indexed file; used to detect invalid-key conditions during random account reads"

  - name: "TRANFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file status code for the posted-transaction VSAM indexed file"

  - name: "IO-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Staging area that holds the file status code from the most recently failed I/O operation before it is formatted and displayed by Z-DISPLAY-IO-STATUS"

  # REDEFINES pair — binary integer vs. two-byte character overlay
  - name: "TWO-BYTES-BINARY"
    level: 01
    picture: "9(4)"
    usage: "BINARY"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-byte binary integer workspace used to convert a single file-status character (IO-STAT2) into a displayable three-digit decimal number for non-standard status codes"

  - name: "TWO-BYTES-ALPHA"
    level: 01
    picture: null
    usage: "BINARY"
    value: null
    redefines: "TWO-BYTES-BINARY"
    redefines_interpretations:
      - condition: "IO-STAT1 = '9' (non-numeric, vendor-specific file status in IO-STATUS)"
        interpreted_as: "Two single-character fields (TWO-BYTES-LEFT and TWO-BYTES-RIGHT) overlaying the same two bytes; IO-STAT2 is moved into TWO-BYTES-RIGHT so that TWO-BYTES-BINARY can be read as an integer for display"
        encoding: "DISPLAY"
      - condition: "IO-STATUS is numeric and IO-STAT1 is not '9' (standard ANSI file status)"
        interpreted_as: "The two bytes are treated as a packed integer holding the numeric file status value, allowing it to be extracted and moved into the three-digit display field IO-STATUS-0403"
        encoding: "BINARY"
    dead_code_flag: false
    semantic: "Character overlay of TWO-BYTES-BINARY; exposes left and right byte positions independently so that non-numeric file status codes can be decomposed and converted to a printable four-character diagnostic string"

  - name: "IO-STATUS-04"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Four-character formatted I/O status diagnostic buffer composed of a one-digit severity prefix (IO-STATUS-0401) and a three-digit numeric status code (IO-STATUS-0403); displayed to the operator on error"

  - name: "APPL-RESULT"
    level: 01
    picture: "S9(9)"
    usage: "COMP"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Signed 9-digit binary application return code set after each file operation; condition name APPL-AOK (value 0) signals success, APPL-EOF (value 16) signals end-of-file, and any other non-zero value triggers abend"

  - name: "END-OF-DAILY-TRANS-FILE"
    level: 01
    picture: "X(01)"
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Single-character end-of-file sentinel; initialized to 'N' and set to 'Y' when the daily transaction file returns a status-10 (end-of-file) condition, terminating the main processing loop"

  - name: "ABCODE"
    level: 01
    picture: "S9(9)"
    usage: "BINARY"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Abend code passed to the Language Environment CEE3ABD service; set to 999 before the abnormal termination call"

  - name: "TIMING"
    level: 01
    picture: "S9(9)"
    usage: "BINARY"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Timing parameter passed to CEE3ABD alongside ABCODE; set to 0 (immediate abend) before each abnormal termination call"

  - name: "WS-MISC-VARIABLES"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Group item holding runtime read-status accumulators for the cross-reference and account file lookups; used to gate downstream processing within the main transaction loop"

# ── Procedure Paragraphs ───────────────────────────────────────────────────────
procedure_paragraphs:
  - name: "MAIN-PARA"
    reachable: true
    performs:
      - "0000-DALYTRAN-OPEN"
      - "0100-CUSTFILE-OPEN"
      - "0200-XREFFILE-OPEN"
      - "0300-CARDFILE-OPEN"
      - "0400-ACCTFILE-OPEN"
      - "0500-TRANFILE-OPEN"
      - "1000-DALYTRAN-GET-NEXT"
      - "2000-LOOKUP-XREF"
      - "3000-READ-ACCOUNT"
      - "9000-DALYTRAN-CLOSE"
      - "9100-CUSTFILE-CLOSE"
      - "9200-XREFFILE-CLOSE"
      - "9300-CARDFILE-CLOSE"
      - "9400-ACCTFILE-CLOSE"
      - "9500-TRANFILE-CLOSE"
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Program entry point that opens all six files, drives the sequential read-validate loop over the daily transaction file, and closes all files before returning control to the operating system via GOBACK"

  - name: "END-PERFORM"
    reachable: false
    performs: []
    goto_targets: []
    summary: "CFG artifact node representing the syntactic end of the PERFORM UNTIL loop in MAIN-PARA; not a separately callable paragraph and marked unreachable by static analysis"

  - name: "GOBACK"
    reachable: false
    performs: []
    goto_targets: []
    summary: "CFG artifact node representing the GOBACK statement that returns control to the caller; marked unreachable by static analysis as it is reached only via fall-through from the last executable statement in MAIN-PARA"

  - name: "1000-DALYTRAN-GET-NEXT"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Reads the next record from the daily transaction sequential file into working storage, sets APPL-RESULT to reflect success, end-of-file, or error, and abends on any unexpected I/O failure"

  - name: "2000-LOOKUP-XREF"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Performs a random keyed read of the card cross-reference VSAM file using the card number from the current transaction record, setting WS-XREF-READ-STATUS to 4 if the card number is not found"

  - name: "END-READ"
    reachable: false
    performs: []
    goto_targets: []
    summary: "CFG artifact node representing the syntactic END-READ delimiter within 2000-LOOKUP-XREF; not a callable paragraph and marked unreachable by static analysis"

  - name: "3000-READ-ACCOUNT"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Performs a random keyed read of the account VSAM file using the account identifier resolved from the cross-reference record, setting WS-ACCT-READ-STATUS to 4 if the account is not found"

  - name: "0000-DALYTRAN-OPEN"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens the daily transaction sequential file for input and abends the program if the open fails"

  - name: "0100-CUSTFILE-OPEN"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens the customer VSAM indexed file for input and abends the program if the open fails"

  - name: "0200-XREFFILE-OPEN"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens the card cross-reference VSAM indexed file for input and abends the program if the open fails"

  - name: "0300-CARDFILE-OPEN"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens the card detail VSAM indexed file for input and abends the program if the open fails"

  - name: "0400-ACCTFILE-OPEN"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens the account VSAM indexed file for input and abends the program if the open fails"

  - name: "0500-TRANFILE-OPEN"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens the posted-transaction VSAM indexed file for input and abends the program if the open fails"

  - name: "9000-DALYTRAN-CLOSE"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Closes the daily transaction sequential file and abends the program if the close operation fails"

  - name: "9100-CUSTFILE-CLOSE"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Closes the customer VSAM indexed file and abends the program if the close operation fails"

  - name: "9200-XREFFILE-CLOSE"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Closes the card cross-reference VSAM indexed file and abends the program if the close operation fails"

  - name: "9300-CARDFILE-CLOSE"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Closes the card detail VSAM indexed file and abends the program if the close operation fails"

  - name: "9400-ACCTFILE-CLOSE"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Closes the account VSAM indexed file and abends the program if the close operation fails"

  - name: "9500-TRANFILE-CLOSE"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Closes the posted-transaction VSAM indexed file and abends the program if the close operation fails"

  - name: "Z-ABEND-PROGRAM"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Sets ABCODE to 999 and TIMING to 0 then calls the Language Environment CEE3ABD service to force an abnormal termination with a user abend code, terminating the job step"

  - name: "Z-DISPLAY-IO-STATUS"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Formats the two-character IO-STATUS into a four-character printable diagnostic string (handling both numeric and non-numeric status codes) and displays it to the operator before an abend"

# ── Business Rules ─────────────────────────────────────────────────────────────
business_rules:
  - id: "BR-001"
    rule: "All six files (daily transaction, customer, cross-reference, card, account, and posted-transaction) must be successfully opened before any transaction processing begins; a failure on any file open triggers an immediate abend with CEE3ABD code 999"
    source_paragraph: "MAIN-PARA"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-002"
    rule: "The main processing loop continues reading and validating transaction records sequentially until the daily transaction file signals end-of-file, at which point the sentinel END-OF-DAILY-TRANS-FILE is set to 'Y' and the loop terminates"
    source_paragraph: "MAIN-PARA"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-003"
    rule: "Each transaction record read from the daily file is immediately displayed to the system log before any cross-reference lookup is performed, provided end-of-file has not been reached"
    source_paragraph: "MAIN-PARA"
    rule_type: "display"
    confidence: "high"
    reachable: true

  - id: "BR-004"
    rule: "The card number extracted from each daily transaction record must be validated against the card cross-reference VSAM file; if the card number is not found (WS-XREF-READ-STATUS is set to 4), the transaction is skipped with a diagnostic message and no account lookup is attempted"
    source_paragraph: "MAIN-PARA"
    rule_type: "lookup"
    confidence: "high"
    reachable: true

  - id: "BR-005"
    rule: "When a card number cannot be verified in the cross-reference file, a diagnostic message identifying the unverifiable card number and the skipped transaction identifier is written to the operator console, and the transaction record is abandoned without further processing"
    source_paragraph: "MAIN-PARA"
    rule_type: "audit"
    confidence: "high"
    reachable: true

  - id: "BR-006"
    rule: "Only when cross-reference lookup succeeds (WS-XREF-READ-STATUS equals zero) is the resolved account identifier used to perform a further lookup against the account VSAM file"
    source_paragraph: "MAIN-PARA"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-007"
    rule: "If the account record resolved through the cross-reference is not found in the account VSAM file (WS-ACCT-READ-STATUS is non-zero), a diagnostic message naming the missing account identifier is displayed, but no abend is triggered and processing continues with the next transaction"
    source_paragraph: "MAIN-PARA"
    rule_type: "audit"
    confidence: "high"
    reachable: true

  - id: "BR-008"
    rule: "A read of the daily transaction file that returns a status code other than '00' (success) or '10' (end-of-file) is treated as an unrecoverable I/O error: the status code is formatted and displayed, then CEE3ABD is called with abend code 999 to terminate the job"
    source_paragraph: "1000-DALYTRAN-GET-NEXT"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-009"
    rule: "A status code of '10' returned from the daily transaction file read is the only normal termination signal; it sets END-OF-DAILY-TRANS-FILE to 'Y', which causes the PERFORM UNTIL loop to exit cleanly"
    source_paragraph: "1000-DALYTRAN-GET-NEXT"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-010"
    rule: "When a random read of the cross-reference VSAM file returns INVALID KEY, the card number is flagged as unverifiable by setting WS-XREF-READ-STATUS to 4, and a diagnostic message is written to the console"
    source_paragraph: "2000-LOOKUP-XREF"
    rule_type: "lookup"
    confidence: "high"
    reachable: true

  - id: "BR-011"
    rule: "When a random read of the account VSAM file returns INVALID KEY, WS-ACCT-READ-STATUS is set to 4 and a diagnostic message is written to the console; the condition is non-fatal and processing resumes with the next record"
    source_paragraph: "3000-READ-ACCOUNT"
    rule_type: "lookup"
    confidence: "high"
    reachable: true

  - id: "BR-012"
    rule: "Any file open or close operation that does not return status '00' is mapped to APPL-RESULT value 12 (error), which causes Z-DISPLAY-IO-STATUS and Z-ABEND-PROGRAM to be called, terminating the job with abend code 999"
    source_paragraph: "0000-DALYTRAN-OPEN"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-013"
    rule: "Non-numeric file status codes (IO-STAT1 equal to '9') are decoded by overlaying TWO-BYTES-BINARY with TWO-BYTES-ALPHA so that the vendor-specific second byte can be converted to a displayable three-digit decimal before operator notification"
    source_paragraph: "Z-DISPLAY-IO-STATUS"
    rule_type: "transform"
    confidence: "high"
    reachable: true

# ── Validation Status ──────────────────────────────────────────────────────────
validation:
  t01_schema_valid: null
  t02_structural_complete: null
  t02r_redefines_complete: null
  t03_functional_score: null
  t04_semantic_score: null
  t05_regression_pass: null
  overall: "PENDING"
---

# CBTRN01C — Daily Transaction File Processor and Cross-Reference Validator

## Purpose

CBTRN01C is a batch COBOL program in the CardDemo application that reads a daily transaction file sequentially and validates each transaction record against a set of VSAM reference files. For every incoming transaction, the program verifies that the card number can be resolved to an account via the card cross-reference file, and then confirms that the resolved account exists in the account master file. The program serves as the first-stage intake filter for the daily transaction posting pipeline, surfacing data-quality problems through operator console messages and aborting the job on unrecoverable I/O errors.

## Runtime Context

The program executes as a z/OS batch job step under IBM Enterprise COBOL with no CICS or DB2 involvement. It opens six VSAM or sequential files at startup — the daily transaction sequential input file (DALYTRAN), a customer indexed file (CUSTFILE), a card-to-account cross-reference indexed file (XREFFILE), a card detail indexed file (CARDFILE), an account indexed file (ACCTFILE), and a posted-transaction indexed file (TRANFILE) — performs all processing in memory, and closes all six files before returning. The program makes one outbound static call: to the Language Environment service CEE3ABD, which is invoked exclusively on unrecoverable error paths to force a user abend with code 999. No records are written or updated during normal processing; the program is read-only against all VSAM stores. Operator diagnostics are emitted to the system console via DISPLAY statements throughout.

## Data Layout

### File Section Records

The file section defines six root-level record layouts, one per file. The daily transaction record (FD-TRAN-RECORD) presents a 16-character transaction identifier field followed by 334 bytes of unstructured payload; the detailed field decomposition for the payload is supplied by the CVTRA06Y copybook, which overlays the working-storage copy area DALYTRAN-RECORD. The customer file record (FD-CUSTFILE-REC) exposes a 9-digit numeric primary key (FD-CUST-ID) and a 491-byte data area; its working-storage expansion is provided by CVCUS01Y. The cross-reference file record (FD-XREFFILE-REC) exposes a 16-character card number key (FD-XREF-CARD-NUM) and a 34-byte data area; its detail layout is provided by CVACT03Y. The card file record (FD-CARDFILE-REC) exposes a 16-character card number (FD-CARD-NUM) and a 134-byte data area; its layout is provided by CVACT02Y. The account file record (FD-ACCTFILE-REC) exposes an 11-digit numeric account key (FD-ACCT-ID) and a 289-byte data area; its layout is provided by CVACT01Y. The posted-transaction file record (FD-TRANFILE-REC) exposes a 16-character transaction key (FD-TRANS-ID) and a 334-byte data area; its layout is provided by CVTRA05Y.

### File Status and I/O Control Areas

Each of the six files has a corresponding two-character file status working-storage group (DALYTRAN-STATUS, CUSTFILE-STATUS, XREFFILE-STATUS, CARDFILE-STATUS, ACCTFILE-STATUS, TRANFILE-STATUS), each split into a left character (first status digit) and a right character (second status digit). A shared staging area, IO-STATUS, receives a copy of the failing file's status code before error display.

### REDEFINES: TWO-BYTES-BINARY / TWO-BYTES-ALPHA

The single REDEFINES clause in this program overlays a two-byte binary integer (TWO-BYTES-BINARY, a 4-digit binary field occupying two bytes) with a character group (TWO-BYTES-ALPHA) that exposes the same storage as two independent single-character fields: TWO-BYTES-LEFT and TWO-BYTES-RIGHT.

The runtime selection between the two interpretations is driven by the value of IO-STAT1 within the IO-STATUS group. When IO-STAT1 equals the character '9' — indicating a vendor-specific, non-standard file status — the I/O status display logic moves the right-hand byte (IO-STAT2) into TWO-BYTES-RIGHT via the character view, then reads TWO-BYTES-BINARY as an integer to obtain the numeric equivalent for display. When IO-STAT1 is not '9' and IO-STATUS is fully numeric — indicating a standard ANSI file status — the two bytes are treated as a packed integer value directly, and the numeric status is moved into the three-digit display field IO-STATUS-0403.

This dual-interpretation mechanism is necessary because IBM z/OS file systems can return non-numeric status codes (beginning with '9') for hardware- or vendor-specific error conditions, which cannot be handled by simple numeric formatting.

### Application Result and Sentinel Flags

APPL-RESULT is a signed binary integer that encodes the outcome of each file operation using condition names: APPL-AOK (value 0) means success, APPL-EOF (value 16) means end-of-file. END-OF-DAILY-TRANS-FILE is a single-character flag initialized to 'N' that acts as the loop termination sentinel. ABCODE and TIMING are binary parameters prepared immediately before each call to CEE3ABD. The WS-MISC-VARIABLES group holds two 4-digit numeric fields — WS-XREF-READ-STATUS and WS-ACCT-READ-STATUS — that capture the outcome of each VSAM random read and gate downstream validation steps.

## Procedure Logic

### MAIN-PARA

The program entry point opens all six files in sequence by performing the six open paragraphs (0000 through 0500). It then enters a PERFORM UNTIL loop that runs as long as END-OF-DAILY-TRANS-FILE is not 'Y'. Within each iteration, if the end-of-file sentinel is still 'N', the program calls 1000-DALYTRAN-GET-NEXT to fetch the next record. If the file is not yet exhausted, the retrieved transaction record is displayed to the console. The card number from the transaction is then moved to the cross-reference key field, WS-XREF-READ-STATUS is zeroed, and 2000-LOOKUP-XREF is called. If the cross-reference lookup succeeds (WS-XREF-READ-STATUS remains zero), WS-ACCT-READ-STATUS is zeroed, the account identifier from the cross-reference record is moved to the account key, and 3000-READ-ACCOUNT is called; if the account is not found, a diagnostic message is displayed. If the cross-reference lookup fails, a diagnostic message naming the unverifiable card number and skipped transaction identifier is displayed and the transaction is abandoned. After the loop exits, the program calls the six close paragraphs (9000 through 9500) in sequence, displays an end-of-execution message, and exits via GOBACK.

### END-PERFORM

This is a CFG artifact node that marks the syntactic boundary of the PERFORM UNTIL construct in MAIN-PARA. It is not a callable paragraph; static analysis marks it unreachable.

### GOBACK

This is a CFG artifact node representing the GOBACK statement at the end of MAIN-PARA. Static analysis marks it unreachable as a standalone node because control reaches it by falling through MAIN-PARA rather than by a separate PERFORM.

### 1000-DALYTRAN-GET-NEXT

This paragraph issues a sequential READ against the daily transaction file, moving the data into the DALYTRAN-RECORD working-storage area. A status of '00' sets APPL-RESULT to zero (APPL-AOK). A status of '10' sets APPL-RESULT to 16 (APPL-EOF), which causes the sentinel END-OF-DAILY-TRANS-FILE to be set to 'Y'. Any other status is treated as an unrecoverable error: the status code is copied to IO-STATUS, Z-DISPLAY-IO-STATUS is called to format and print the error, and Z-ABEND-PROGRAM is called to terminate the job.

### 2000-LOOKUP-XREF

This paragraph moves the card number to the VSAM key field FD-XREF-CARD-NUM and issues a random READ of XREF-FILE using that key. On an INVALID KEY condition — meaning the card number is absent from the cross-reference index — a diagnostic message is displayed and WS-XREF-READ-STATUS is set to 4 to signal failure to the caller. On a successful NOT INVALID KEY condition, the resolved card number, account identifier, and customer identifier from the cross-reference record are displayed to the console and WS-XREF-READ-STATUS remains zero.

### END-READ

This is a CFG artifact node marking the END-READ delimiter inside 2000-LOOKUP-XREF. Static analysis marks it unreachable as a standalone callable unit.

### 3000-READ-ACCOUNT

This paragraph moves the account identifier (resolved from the cross-reference) to the VSAM key field FD-ACCT-ID and issues a random READ of ACCOUNT-FILE. On an INVALID KEY condition, a diagnostic message is displayed and WS-ACCT-READ-STATUS is set to 4. On a successful read, a confirmation message is displayed and WS-ACCT-READ-STATUS remains zero. Unlike a failed cross-reference lookup, a failed account read is non-fatal; the main loop continues to the next transaction.

### 0000-DALYTRAN-OPEN

Sets APPL-RESULT to 8 (tentative error), then opens the daily transaction sequential file for INPUT. If DALYTRAN-STATUS is '00', APPL-RESULT is set to 0 (success). Otherwise it is set to 12 (error). If APPL-RESULT is not APPL-AOK, the error message and status code are displayed and the program abends.

### 0100-CUSTFILE-OPEN

Opens the customer VSAM indexed file for INPUT using the same guard logic as 0000-DALYTRAN-OPEN; abends on any status other than '00'.

### 0200-XREFFILE-OPEN

Opens the card cross-reference VSAM indexed file for INPUT; abends on any status other than '00'.

### 0300-CARDFILE-OPEN

Opens the card detail VSAM indexed file for INPUT; abends on any status other than '00'.

### 0400-ACCTFILE-OPEN

Opens the account VSAM indexed file for INPUT; abends on any status other than '00'.

### 0500-TRANFILE-OPEN

Opens the posted-transaction VSAM indexed file for INPUT; abends on any status other than '00'.

### 9000-DALYTRAN-CLOSE

Closes the daily transaction sequential file using the standard guard pattern; abends if DALYTRAN-STATUS is not '00' after the close.

### 9100-CUSTFILE-CLOSE

Closes the customer VSAM indexed file; abends if CUSTFILE-STATUS is not '00'.

### 9200-XREFFILE-CLOSE

Closes the card cross-reference VSAM indexed file; abends if XREFFILE-STATUS is not '00'.

### 9300-CARDFILE-CLOSE

Closes the card detail VSAM indexed file; abends if CARDFILE-STATUS is not '00'.

### 9400-ACCTFILE-CLOSE

Closes the account VSAM indexed file; abends if ACCTFILE-STATUS is not '00'.

### 9500-TRANFILE-CLOSE

Closes the posted-transaction VSAM indexed file; abends if TRANFILE-STATUS is not '00'.

### Z-ABEND-PROGRAM

Moves zero to TIMING and 999 to ABCODE, then issues a static call to the IBM Language Environment service CEE3ABD passing ABCODE and TIMING. This forces an immediate user abend, writing a dump and setting the job step return code to a non-zero value. There is no return from this paragraph under any circumstances.

### Z-DISPLAY-IO-STATUS

Examines IO-STATUS to determine whether the status code is numeric and whether IO-STAT1 is not the character '9'. For standard ANSI numeric status codes, a four-character display string is constructed by placing '00' in the leading positions and moving the two-character status into the trailing positions. For non-numeric or vendor-specific codes (IO-STAT1 equals '9'), the TWO-BYTES-ALPHA redefine is used to copy IO-STAT2 into the right byte of TWO-BYTES-BINARY, whose integer value is then moved to IO-STATUS-0403 for display. In both branches the formatted four-character status string is emitted to the operator console.

## Business Rules Surfaced

**BR-001** — All six files must open successfully before any transaction is processed; failure on any file open causes an immediate job abend with code 999.

**BR-002** — The processing loop iterates until the daily transaction file signals end-of-file, at which point END-OF-DAILY-TRANS-FILE is set to 'Y' and the loop exits cleanly.

**BR-003** — Every successfully read transaction record is echoed to the system console before cross-reference validation begins.

**BR-004** — Each transaction's card number must resolve to an entry in the cross-reference VSAM file; an INVALID KEY result (WS-XREF-READ-STATUS = 4) causes the transaction to be skipped entirely.

**BR-005** — When a card number cannot be verified, a console message identifying the card number and the associated transaction identifier is issued, providing an audit trail of skipped transactions.

**BR-006** — Account lookup (3000-READ-ACCOUNT) is only performed when the cross-reference lookup succeeds; WS-XREF-READ-STATUS must be zero before the account read is attempted.

**BR-007** — A missing account record (WS-ACCT-READ-STATUS non-zero) is logged to the console but is non-fatal; the program continues processing subsequent transactions rather than aborting.

**BR-008** — Any daily transaction file read status other than '00' or '10' is an unrecoverable error that causes the status to be formatted and displayed, then triggers CEE3ABD abend code 999.

**BR-009** — A file status of '10' on the daily transaction read is the sole normal termination condition; it sets the end-of-file sentinel and terminates the loop.

**BR-010** — A failed XREF-FILE random read (INVALID KEY) sets WS-XREF-READ-STATUS to 4 and writes a diagnostic to the console.

**BR-011** — A failed ACCOUNT-FILE random read (INVALID KEY) sets WS-ACCT-READ-STATUS to 4 and writes a diagnostic to the console, but does not abort processing.

**BR-012** — Any file open or close that returns a status other than '00' sets APPL-RESULT to 12 and triggers Z-DISPLAY-IO-STATUS followed by Z-ABEND-PROGRAM, terminating the job.

**BR-013** — Non-numeric (vendor-specific) file status codes are decoded by using the TWO-BYTES-ALPHA character overlay of TWO-BYTES-BINARY to extract and convert the second byte into a printable three-digit decimal before display.

## Graph Summary

- **CALLS**: CBTRN01C —[STATIC, on unrecoverable I/O error]--> CEE3ABD
- **COPYBOOKS**: CBTRN01C uses CVTRA06Y (daily transaction record layout), CVCUS01Y (customer record layout), CVACT03Y (card cross-reference record layout), CVACT02Y (card detail record layout), CVACT01Y (account record layout), CVTRA05Y (posted-transaction record layout)
- **VSAM READS**: CBTRN01C reads DALYTRAN (sequential, all records), XREFFILE (random by card number, each transaction), ACCTFILE (random by account ID, each verified transaction)
- **VSAM OPENS (read-only, no writes)**: CUSTFILE, CARDFILE, TRANFILE opened for input but no records are read from them in the current implementation
- **RULES**: BR-001 (guard — all files must open), BR-002 (guard — EOF terminates loop), BR-003 (display — echo each transaction), BR-004 (lookup — card-xref guard), BR-005 (audit — skip message for unverifiable card), BR-006 (guard — xref success gates account lookup), BR-007 (audit — missing account non-fatal), BR-008 (guard — read error abends job), BR-009 (guard — EOF-10 terminates normally), BR-010 (lookup — xref INVALID KEY), BR-011 (lookup — account INVALID KEY), BR-012 (guard — open/close error abends job), BR-013 (transform — non-numeric status decoding)
- **DEAD CODE**: END-PERFORM, GOBACK, and END-READ are CFG artifact nodes marked unreachable by static analysis; no live code paragraphs are unreachable
- **ABEND PATHS**: Any file open failure, any file close failure, or any daily transaction read error other than end-of-file calls Z-DISPLAY-IO-STATUS then Z-ABEND-PROGRAM (CEE3ABD, code 999); no GOTO statements exist in this program
