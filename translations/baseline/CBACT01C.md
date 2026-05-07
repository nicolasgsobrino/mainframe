---
# ── Identity ──────────────────────────────────────────────────────────────────
schema_version: "cobol-md/1.0"
program_id: "CBACT01C"
source_file: "app/cbl/CBACT01C.cbl"
source_sha: "a9a14e021e6fe1c14caa544213d938abd15b6681"
translation_date: "2026-04-23"
translating_agent: "claude-opus-4-5 (subagent)"
aifirst_task_id: "T-2026-04-23-001"
cfg_source: "validation/structure/CBACT01C_cfg.json"

# ── Classification ─────────────────────────────────────────────────────────────
business_domain: "Account Management"
subtype: "Batch"

# ── Structural Metadata ────────────────────────────────────────────────────────
author: "AWS"
date_written: null
lines_of_code: 248
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
  - program: "COBDATFT"
    condition: "unconditional"
    call_type: "STATIC"
  - program: "CEE3ABD"
    condition: "fatal I/O or open/close failure detected"
    call_type: "STATIC"

called_by: []

copybooks_used:
  - name: "CVACT01Y"
    path: "app/cpy/CVACT01Y.cpy"
    sha: null
  - name: "CODATECN"
    path: "app/cpy/CODATECN.cpy"
    sha: null

# ── File I/O ──────────────────────────────────────────────────────────────────
file_control:
  - ddname: "ACCTFILE"
    organization: "INDEXED"
    access: "SEQUENTIAL"
    record_key: "FD-ACCT-ID"
    crud: ["READ"]
  - ddname: "OUTFILE"
    organization: "SEQUENTIAL"
    access: "SEQUENTIAL"
    record_key: null
    crud: ["CREATE"]
  - ddname: "ARRYFILE"
    organization: "SEQUENTIAL"
    access: "SEQUENTIAL"
    record_key: null
    crud: ["CREATE"]
  - ddname: "VBRCFILE"
    organization: "SEQUENTIAL"
    access: "SEQUENTIAL"
    record_key: null
    crud: ["CREATE"]

# ── CICS ───────────────────────────────────────────────────────────────────────
cics_commands: []
transaction_ids: []

# ── Data Layer ─────────────────────────────────────────────────────────────────
data_items:
  - name: "FD-ACCTFILE-REC"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "File descriptor group record for the VSAM KSDS account input file; top-level container for FD-ACCT-ID and FD-ACCT-DATA"

  - name: "OUT-ACCT-REC"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Output record written to the sequential OUTFILE; contains a fully expanded, formatted account snapshot for downstream consumption"

  - name: "ARR-ARRAY-REC"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Output record written to the sequential ARRYFILE; holds the account identifier plus a five-element balance array for multi-cycle reporting"

  - name: "VBR-REC"
    level: 01
    picture: "X(80)"
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Variable-length output buffer for VBRCFILE; receives short (12-byte) or long (39-byte) segments depending on which record variant is being written"

  - name: "ACCTFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file-status code returned by the runtime after every I/O operation on ACCTFILE; first byte is class, second is subclass"

  - name: "OUTFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file-status code for OUTFILE I/O operations"

  - name: "ARRYFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file-status code for ARRYFILE I/O operations"

  - name: "VBRCFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character file-status code for VBRCFILE I/O operations"

  - name: "IO-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Staging area that receives any file-status value immediately before calling the I/O status display routine; normalises status from multiple files into one display path"

  - name: "TWO-BYTES-BINARY"
    level: 01
    picture: "9(4)"
    usage: "BINARY"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Four-digit binary integer occupying two bytes; used as the numeric form of an I/O status code when decoding non-numeric or VSAM extended status bytes"

  - name: "TWO-BYTES-ALPHA"
    level: 01
    picture: null
    usage: "BINARY"
    value: null
    redefines: "TWO-BYTES-BINARY"
    redefines_interpretations:
      - condition: "IO-STAT1 = '9' (VSAM extended status path in 9910-DISPLAY-IO-STATUS)"
        interpreted_as: "Two individual character bytes (left and right) overlaying the binary integer, allowing the second status byte to be extracted as a raw character and then converted to a numeric value for display"
        encoding: "DISPLAY"
      - condition: "IO-STATUS is numeric and IO-STAT1 != '9' (standard status path in 9910-DISPLAY-IO-STATUS)"
        interpreted_as: "Two-byte binary integer holding a packed numeric I/O status code; not decomposed into left/right characters in this path; the integer value is moved directly to IO-STATUS-0403 for formatted display"
        encoding: "BINARY"
    dead_code_flag: false
    semantic: "Character alias for TWO-BYTES-BINARY; provides byte-level access to the two halves of the binary status word so that VSAM extended return codes can be decoded and printed"

  - name: "IO-STATUS-04"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Four-character display buffer for printing a normalised I/O status code; composed of a one-digit class subfield and a three-digit subclass subfield"

  - name: "APPL-RESULT"
    level: 01
    picture: "S9(9)"
    usage: "COMP"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Signed nine-digit binary working register used to communicate operation outcome within each I/O routine; value 0 = success (APPL-AOK), 16 = end-of-file (APPL-EOF), 12 = error"

  - name: "END-OF-FILE"
    level: 01
    picture: "X(01)"
    usage: null
    value: "N"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Single-character flag controlling the main read loop; initialised to 'N' and set to 'Y' when ACCTFILE reaches end-of-file, terminating the PERFORM UNTIL loop"

  - name: "ABCODE"
    level: 01
    picture: "S9(9)"
    usage: "BINARY"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Abend code passed to CEE3ABD when the program terminates abnormally; always set to 999 before the abend call"

  - name: "TIMING"
    level: 01
    picture: "S9(9)"
    usage: "BINARY"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Timing parameter passed to CEE3ABD alongside ABCODE; set to 0 indicating immediate (non-delayed) abend"

  - name: "WS-RECD-LEN"
    level: 01
    picture: "9(04)"
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Four-digit unsigned integer specifying the logical length of the current variable-length record before writing to VBRCFILE; set to 12 for the short variant and 39 for the long variant"

  - name: "VBRC-REC1"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Short variable-length record layout containing account identifier (11 digits) and active-status flag (1 character) for the first VBRCFILE write"

  - name: "VBRC-REC2"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Long variable-length record layout containing account identifier, current balance, credit limit, and reissue year for the second VBRCFILE write"

  - name: "WS-ACCT-REISSUE-DATE"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Structured working-storage date group that holds a card reissue date parsed into separate year (4 chars), separator, month (2 chars), separator, and day (2 chars) subfields"

  - name: "WS-REISSUE-DATE"
    level: 01
    picture: "X(10)"
    usage: null
    value: null
    redefines: "WS-ACCT-REISSUE-DATE"
    redefines_interpretations:
      - condition: "WS-REISSUE-DATE is being populated from ACCT-REISSUE-DATE in the account record (in 1300-POPUL-ACCT-RECORD, before date formatting)"
        interpreted_as: "Flat ten-character string view of the reissue date, allowing the entire date to be moved as a single unit from the source account record field into the structured date group in one operation"
        encoding: "DISPLAY"
      - condition: "WS-ACCT-REISSUE-YYYY is being referenced after the flat move (in 1500-POPUL-VBRC-RECORD, extracting the year component)"
        interpreted_as: "Structured date group with individually addressable subfields (year, separator, month, separator, day), enabling the program to extract the four-character year portion independently for population of VB2-ACCT-REISSUE-YYYY"
        encoding: "DISPLAY"
    dead_code_flag: false
    semantic: "Flat ten-character alias for WS-ACCT-REISSUE-DATE; enables bulk assignment of the full date string while WS-ACCT-REISSUE-DATE provides field-level access to individual date components"

# ── Procedure Paragraphs ───────────────────────────────────────────────────────
procedure_paragraphs:
  - name: "END-PERFORM"
    reachable: true
    performs:
      - "0000-ACCTFILE-OPEN"
      - "2000-OUTFILE-OPEN"
      - "3000-ARRFILE-OPEN"
      - "4000-VBRFILE-OPEN"
      - "1000-ACCTFILE-GET-NEXT"
      - "9000-ACCTFILE-CLOSE"
      - "1100-DISPLAY-ACCT-RECORD"
      - "1300-POPUL-ACCT-RECORD"
      - "1350-WRITE-ACCT-RECORD"
      - "1400-POPUL-ARRAY-RECORD"
      - "1450-WRITE-ARRY-RECORD"
      - "1500-POPUL-VBRC-RECORD"
      - "1550-WRITE-VB1-RECORD"
      - "1575-WRITE-VB2-RECORD"
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Implicit main control block (the procedure division body before the first named paragraph): opens all four output files, drives the PERFORM UNTIL read loop over ACCTFILE, closes ACCTFILE, and issues GOBACK"

  - name: "GOBACK"
    reachable: false
    performs: []
    goto_targets: []
    summary: "CFG artefact node representing the program return point; marked unreachable by static analysis because the GOBACK statement is embedded in the top-level implicit paragraph and the CFG tool emitted it as a separate, unreachable node"

  - name: "1000-ACCTFILE-GET-NEXT"
    reachable: true
    performs:
      - "1100-DISPLAY-ACCT-RECORD"
      - "1300-POPUL-ACCT-RECORD"
      - "1350-WRITE-ACCT-RECORD"
      - "1400-POPUL-ARRAY-RECORD"
      - "1450-WRITE-ARRY-RECORD"
      - "1500-POPUL-VBRC-RECORD"
      - "1550-WRITE-VB1-RECORD"
      - "1575-WRITE-VB2-RECORD"
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Reads the next account record from ACCTFILE, evaluates the file status to set APPL-RESULT, and on success drives all display and write sub-paragraphs; on end-of-file sets END-OF-FILE to 'Y'; on any other error displays status and abends"

  - name: "1100-DISPLAY-ACCT-RECORD"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Prints all eleven account fields from the ACCOUNT-RECORD copybook area to standard output as a labelled diagnostic listing, followed by a separator line"

  - name: "1300-POPUL-ACCT-RECORD"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Maps account fields from the input ACCOUNT-RECORD into the OUT-ACCT-REC output layout, calls the COBDATFT date-formatting sub-routine to convert the reissue date, and applies a default debit value of 2525.00 when the current-cycle debit amount is zero"

  - name: "WS-REISSUE-DATE"
    reachable: false
    performs: []
    goto_targets: []
    summary: "CFG artefact node corresponding to the WS-REISSUE-DATE data-item name; emitted as a procedure paragraph by the CFG tool in error — it is a working-storage REDEFINES item, not an executable paragraph, and is marked unreachable"

  - name: "END-IF"
    reachable: false
    performs: []
    goto_targets: []
    summary: "CFG artefact node representing an END-IF scope terminator; marked unreachable by the static analysis tool and does not correspond to an actual named paragraph in the source"

  - name: "1350-WRITE-ACCT-RECORD"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Writes the populated OUT-ACCT-REC to OUTFILE and abends if the resulting file status is not successful"

  - name: "1400-POPUL-ARRAY-RECORD"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Builds the ARR-ARRAY-REC output record by copying account ID and current balance into the first two balance-array slots and loading hard-coded test amounts for cycles one through three"

  - name: "1450-WRITE-ARRY-RECORD"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Writes the populated ARR-ARRAY-REC to ARRYFILE and abends if the file status indicates an error"

  - name: "1500-POPUL-VBRC-RECORD"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Populates both variable-length record staging areas (VBRC-REC1 and VBRC-REC2) from the current account record and displays their content for diagnostic purposes"

  - name: "VB2-ACCT-ID"
    reachable: false
    performs: []
    goto_targets: []
    summary: "CFG artefact node corresponding to the VB2-ACCT-ID data-item name; emitted as a procedure paragraph by the CFG tool in error — it is a working-storage field inside VBRC-REC2, not an executable paragraph, and is marked unreachable"

  - name: "1550-WRITE-VB1-RECORD"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Sets the record length to 12, copies VBRC-REC1 into the VBR-REC buffer, writes the short variable-length record to VBRCFILE, and abends on write failure"

  - name: "1575-WRITE-VB2-RECORD"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Sets the record length to 39, copies VBRC-REC2 into the VBR-REC buffer, writes the long variable-length record to VBRCFILE, and abends on write failure"

  - name: "0000-ACCTFILE-OPEN"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens ACCTFILE for sequential input, checks that the file status is successful, and abends with a diagnostic message if the open fails"

  - name: "2000-OUTFILE-OPEN"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens OUTFILE for output, checks file status, and abends with a diagnostic message if the open fails"

  - name: "3000-ARRFILE-OPEN"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens ARRYFILE for output, checks file status, and abends with a diagnostic message if the open fails"

  - name: "4000-VBRFILE-OPEN"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens VBRCFILE for output in variable-length recording mode, checks file status, and abends with a diagnostic message if the open fails"

  - name: "9000-ACCTFILE-CLOSE"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Closes ACCTFILE after the read loop completes and abends if the close operation does not return a successful status"

  - name: "9999-ABEND-PROGRAM"
    reachable: true
    performs:
      - "9910-DISPLAY-IO-STATUS"
    goto_targets: []
    summary: "Displays an abend notification message, sets abend code 999 with zero timing, and calls the Language Environment CEE3ABD service to force a controlled abnormal termination"

  - name: "9910-DISPLAY-IO-STATUS"
    reachable: true
    performs:
      - "9999-ABEND-PROGRAM"
    goto_targets: []
    summary: "Decodes and displays the two-byte I/O status code in a normalised four-digit format, handling both standard numeric status codes and VSAM extended (non-numeric or '9x') status codes"

# ── Business Rules ─────────────────────────────────────────────────────────────
business_rules:
  - id: "BR-001"
    rule: "The main read loop continues only while END-OF-FILE equals 'N'; once any read sets END-OF-FILE to 'Y', the program exits the loop and proceeds to file close and termination"
    source_paragraph: "END-PERFORM"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-002"
    rule: "If a successful read (file status '00') is obtained from ACCTFILE, all downstream populate-and-write paragraphs are executed; no processing occurs for a record when the status is not '00'"
    source_paragraph: "1000-ACCTFILE-GET-NEXT"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-003"
    rule: "A file status of '10' from ACCTFILE is interpreted as normal end-of-file (sets APPL-RESULT to 16, which satisfies APPL-EOF), causing a clean loop exit; any other non-zero status is treated as an error and triggers an abend"
    source_paragraph: "1000-ACCTFILE-GET-NEXT"
    rule_type: "audit"
    confidence: "high"
    reachable: true

  - id: "BR-004"
    rule: "If the current-cycle debit amount on an account record is exactly zero, the output field is overridden with the hard-coded default value of 2525.00 before writing to OUTFILE"
    source_paragraph: "1300-POPUL-ACCT-RECORD"
    rule_type: "transform"
    confidence: "high"
    reachable: true

  - id: "BR-005"
    rule: "Any file open that returns a status other than '00' is treated as fatal; the program displays the status and abends immediately without attempting to proceed"
    source_paragraph: "0000-ACCTFILE-OPEN"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-006"
    rule: "Any file open for OUTFILE that returns a status other than '00' is treated as fatal and triggers an immediate abend"
    source_paragraph: "2000-OUTFILE-OPEN"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-007"
    rule: "Any file open for ARRYFILE that returns a status other than '00' is treated as fatal and triggers an immediate abend"
    source_paragraph: "3000-ARRFILE-OPEN"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-008"
    rule: "Any file open for VBRCFILE that returns a status other than '00' is treated as fatal and triggers an immediate abend"
    source_paragraph: "4000-VBRFILE-OPEN"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-009"
    rule: "Each write to OUTFILE is validated; a file status other than '00' or '10' is treated as a fatal write error, triggers display of the status, and abends the program"
    source_paragraph: "1350-WRITE-ACCT-RECORD"
    rule_type: "audit"
    confidence: "high"
    reachable: true

  - id: "BR-010"
    rule: "Each write to ARRYFILE is validated; a file status other than '00' or '10' triggers a fatal abend"
    source_paragraph: "1450-WRITE-ARRY-RECORD"
    rule_type: "audit"
    confidence: "high"
    reachable: true

  - id: "BR-011"
    rule: "Each write of the short variable-length record to VBRCFILE is validated; a file status other than '00' or '10' triggers a fatal abend"
    source_paragraph: "1550-WRITE-VB1-RECORD"
    rule_type: "audit"
    confidence: "high"
    reachable: true

  - id: "BR-012"
    rule: "Each write of the long variable-length record to VBRCFILE is validated; a file status other than '00' or '10' triggers a fatal abend"
    source_paragraph: "1575-WRITE-VB2-RECORD"
    rule_type: "audit"
    confidence: "high"
    reachable: true

  - id: "BR-013"
    rule: "When an I/O status code is non-numeric or its first character is '9', the status is decoded as a VSAM extended return code by overlaying the binary integer with character bytes and converting the second byte to a numeric value before display"
    source_paragraph: "9910-DISPLAY-IO-STATUS"
    rule_type: "transform"
    confidence: "high"
    reachable: true

  - id: "BR-014"
    rule: "Each account record read from ACCTFILE is displayed in full to standard output before any downstream write processing occurs, providing a complete audit trail of every record encountered"
    source_paragraph: "1100-DISPLAY-ACCT-RECORD"
    rule_type: "display"
    confidence: "high"
    reachable: true

  - id: "BR-015"
    rule: "The ACCTFILE close operation is checked for success; a non-zero status triggers the same abend path used for read and write errors, ensuring file integrity on completion"
    source_paragraph: "9000-ACCTFILE-CLOSE"
    rule_type: "guard"
    confidence: "high"
    reachable: true

# ── Validation Status ──────────────────────────────────────────────────────────
validation:
  t01_schema_valid: true
  t02_structural_complete: true
  t02r_redefines_complete: true
  t03_functional_score: null
  t04_semantic_score: null
  t05_regression_pass: null
  overall: "PASS"
---

# CBACT01C — Account File Sequential Read and Multi-Format Output

## Purpose

CBACT01C is a batch utility program in the CardDemo application that reads every account record from a VSAM Key-Sequenced Data Set (KSDS) sequentially and distributes each record's data into three separate sequential output files in three different structural formats: a flat expanded record, a balance array record, and two variable-length record variants. The program also displays each account record to the standard output stream for diagnostic purposes. It serves as a data extraction and format-conversion batch step within the account management domain.

## Runtime Context

The program runs as a standard z/OS batch job step with no CICS dependency. It accesses five files: one VSAM KSDS input file (ACCTFILE, opened for sequential input with an indexed organisation) and three sequential output files (OUTFILE, ARRYFILE, VBRCFILE). VBRCFILE is opened in variable-length recording mode, with record sizes ranging from 10 to 80 bytes controlled by a working-storage length field. Two external sub-programs are called: COBDATFT, an assembler routine that reformats date strings, and CEE3ABD, the Language Environment abnormal termination service. Two copybooks provide shared data layouts: CVACT01Y defines the canonical account record group (ACCOUNT-RECORD) used as the read target, and CODATECN defines the date-conversion communication record (CODATECN-REC) passed to COBDATFT.

## Data Layout

### Input File Record

The VSAM input file descriptor exposes a two-part record: an eleven-digit unsigned numeric account identifier that also serves as the KSDS primary key, and a 289-character data area that holds all remaining account attributes. At runtime, the READ INTO statement places the raw file record into the ACCOUNT-RECORD structure supplied by the CVACT01Y copybook, which decomposes the 289-byte area into named fields including active status, current balance, credit limit, cash credit limit, open date, expiration date, reissue date, current-cycle credit, current-cycle debit, and group identifier. Monetary balance fields are signed, packed-decimal compatible (twelve digits with two implied decimal places).

### Output Record — Flat Format (OUTFILE)

The OUTFILE record maps directly to the ACCOUNT-RECORD fields and adds formatting: the account identifier, active status, current balance, credit limit, cash credit limit, open date, expiration date, formatted reissue date, current-cycle credit, and current-cycle debit (stored using packed-decimal COMP-3 encoding) are all written as a single fixed-length sequential record. The reissue date is reformatted by COBDATFT before it is placed in this record.

### Output Record — Array Format (ARRYFILE)

The ARRYFILE record groups an eleven-digit account identifier with a five-element balance table. Each table element contains two subfields: a signed twelve-digit balance amount and a signed twelve-digit current-cycle debit stored in COMP-3 packed-decimal encoding. The program only populates three of the five table slots per record; slots four and five are left at their initialised (zero) values. A four-character filler field pads the end of the record.

### Variable-Length Record Staging Areas (VBRCFILE)

Two working-storage records serve as staging buffers for the variable-length output file. The short record (VBRC-REC1) carries the eleven-digit account identifier and the one-character active-status flag, yielding a 12-byte logical record. The long record (VBRC-REC2) carries the account identifier, a signed balance, a signed credit limit, and a four-character reissue year, yielding a 39-byte logical record. Both are moved into the 80-character VBR-REC buffer with an explicit reference modification length before being written.

### REDEFINES Relationships

**TWO-BYTES-ALPHA redefines TWO-BYTES-BINARY.** TWO-BYTES-BINARY is a two-byte binary integer used to hold a numeric I/O status code. TWO-BYTES-ALPHA overlays the same two bytes as a pair of individual character subfields named TWO-BYTES-LEFT and TWO-BYTES-RIGHT. When the I/O status is a VSAM extended code (first byte is '9' or the status is non-numeric), TWO-BYTES-RIGHT is loaded with the raw second status byte and TWO-BYTES-BINARY is then read as an integer to extract the numeric VSAM reason code for display. When the status is a standard numeric code, the binary integer is used directly without invoking the character decomposition. This dual-use pattern is essential for correctly decoding both standard and VSAM-extended file status values from the same two-byte field.

**WS-REISSUE-DATE redefines WS-ACCT-REISSUE-DATE.** WS-ACCT-REISSUE-DATE is a structured ten-byte group containing individually named year, separator, month, separator, and day subfields. WS-REISSUE-DATE overlays those same ten bytes as a single flat character string. The program uses the flat alias to receive the entire reissue date from ACCOUNT-RECORD in a single move operation, and then uses the structured group form to extract just the four-character year component (WS-ACCT-REISSUE-YYYY) when building the long VBRCFILE record. Without this REDEFINES, two separate copy operations or substring reference modification would be required.

## Procedure Logic

### END-PERFORM (Main Control — Implicit Top-Level Body)

The program entry point displays a start-of-execution banner, then serially performs the four file-open paragraphs in order: ACCTFILE (input), OUTFILE, ARRYFILE, and VBRCFILE (all output). It then enters a conditional PERFORM UNTIL loop that continues as long as END-OF-FILE remains 'N'. Inside the loop body, if END-OF-FILE is still 'N', it performs the record-read paragraph (1000-ACCTFILE-GET-NEXT), and if END-OF-FILE remains 'N' after the read, it displays the ACCOUNT-RECORD to standard output. After the loop exits, it performs the ACCTFILE close paragraph, displays an end-of-execution banner, and issues GOBACK to return control to the operating system.

### GOBACK (CFG Node — Static Analysis Artefact)

This node appears in the CFG as unreachable because the static analysis tool emitted the GOBACK statement as a separate paragraph boundary rather than treating it as part of the top-level implicit paragraph. No action is taken here at runtime; the actual GOBACK is executed as part of the implicit main body.

### 1000-ACCTFILE-GET-NEXT

Issues a sequential READ against ACCTFILE, directing the record into the ACCOUNT-RECORD working-storage area. If the file status is '00' (successful), APPL-RESULT is set to zero, the ARR-ARRAY-REC is initialised to spaces/zeros, and the program chains through six sub-paragraphs: display the record, populate and write the flat output record, populate and write the array record, populate the variable-length records and write both the short and long variants. If the file status is '10' (end-of-file), APPL-RESULT is set to 16. Any other status sets APPL-RESULT to 12. After the status branch, a second conditional checks APPL-RESULT: if APPL-AOK (value 0), processing continues normally; if APPL-EOF (value 16), END-OF-FILE is set to 'Y' to trigger loop exit; otherwise, the error display and abend path is taken.

### 1100-DISPLAY-ACCT-RECORD

Emits eleven labelled lines to standard output, one for each named account field from the ACCOUNT-RECORD group (identifier, active status, current balance, credit limit, cash credit limit, open date, expiration date, reissue date, current-cycle credit, current-cycle debit, group identifier), followed by a horizontal separator line. This paragraph serves purely as a diagnostic trace and has no effect on output file content.

### 1300-POPUL-ACCT-RECORD

Copies nine account fields directly from ACCOUNT-RECORD to their corresponding positions in OUT-ACCT-REC. For the reissue date, the raw date string is simultaneously copied to the CODATECN input field and to WS-REISSUE-DATE (the flat alias for the structured date work area), and the date-type codes are set. The external assembler program COBDATFT is then called with the CODATECN-REC communication area to perform date format conversion, and the formatted output date is moved to OUT-ACCT-REISSUE-DATE. The current-cycle credit amount is copied directly. If the current-cycle debit on the input record is zero, OUT-ACCT-CURR-CYC-DEBIT is set to the constant 2525.00 (the default injection rule); otherwise it is not explicitly set in this paragraph (the source data flow suggests the field retains whatever value was present from previous initialisation). Finally, the group identifier is copied.

### WS-REISSUE-DATE (CFG Node — Static Analysis Artefact)

This CFG node was emitted because the tool misidentified the working-storage REDEFINES data item name as a procedure paragraph label. It is not an executable paragraph; it is a data item in working storage and is marked unreachable.

### END-IF (CFG Node — Static Analysis Artefact)

This CFG node represents an END-IF scope terminator that the tool surfaced as a separate unreachable node. It does not correspond to a named paragraph; it is marked unreachable.

### 1350-WRITE-ACCT-RECORD

Issues a WRITE of OUT-ACCT-REC to OUTFILE. If OUTFILE-STATUS is not '00' and not '10', the status value is displayed, moved to IO-STATUS, and the display-and-abend chain is invoked.

### 1400-POPUL-ARRAY-RECORD

Populates the ARR-ARRAY-REC balance table. The account identifier is copied to ARR-ACCT-ID. The current balance is copied to balance-table slot 1's current-balance subfield, and 1005.00 is placed in slot 1's current-cycle-debit subfield. The current balance is also copied to slot 2's balance subfield, and 1525.00 to slot 2's debit subfield. Slot 3 receives hard-coded values of negative 1025.00 for balance and negative 2500.00 for debit. Slots 4 and 5 remain at zero from the earlier INITIALIZE of ARR-ARRAY-REC.

### 1450-WRITE-ARRY-RECORD

Writes ARR-ARRAY-REC to ARRYFILE. If ARRYFILE-STATUS is not '00' and not '10', the status is displayed and the program abends.

### 1500-POPUL-VBRC-RECORD

Populates both variable-length record staging areas from ACCOUNT-RECORD. The account identifier is moved to both VB1-ACCT-ID and VB2-ACCT-ID. VB1-ACCT-ACTIVE-STATUS receives the account active-status flag. VB2-ACCT-CURR-BAL and VB2-ACCT-CREDIT-LIMIT receive the corresponding balance fields. WS-ACCT-REISSUE-YYYY (the year subfield of the structured date group, populated via the WS-REISSUE-DATE flat alias in the earlier paragraph) is moved to VB2-ACCT-REISSUE-YYYY. Both completed records are then displayed to standard output for diagnostic purposes.

### VB2-ACCT-ID (CFG Node — Static Analysis Artefact)

This CFG node was emitted because the tool misidentified the VB2-ACCT-ID data item name inside VBRC-REC2 as a procedure paragraph. It is a working-storage subfield, not an executable paragraph, and is marked unreachable.

### 1550-WRITE-VB1-RECORD

Sets WS-RECD-LEN to 12, uses reference modification to place the first 12 bytes of VBRC-REC1 into VBR-REC, and writes the result to VBRCFILE. Any non-success, non-end-of-file status triggers a display and abend.

### 1575-WRITE-VB2-RECORD

Sets WS-RECD-LEN to 39, uses reference modification to place the first 39 bytes of VBRC-REC2 into VBR-REC, and writes the result to VBRCFILE. Any non-success, non-end-of-file status triggers a display and abend.

### 0000-ACCTFILE-OPEN

Pre-sets APPL-RESULT to 8 (a non-zero sentinel), then opens ACCTFILE for input. If the file status is '00', APPL-RESULT is set to 0 (APPL-AOK); otherwise it is set to 12. If APPL-RESULT is not zero after the open, the program displays 'ERROR OPENING ACCTFILE', moves the status to IO-STATUS, calls 9910-DISPLAY-IO-STATUS, and then calls 9999-ABEND-PROGRAM.

### 2000-OUTFILE-OPEN

Opens OUTFILE for output using the same guard pattern as 0000-ACCTFILE-OPEN; a non-successful open status triggers display of 'ERROR OPENING OUTFILE' and an abend.

### 3000-ARRFILE-OPEN

Opens ARRYFILE for output; a non-successful status triggers display of 'ERROR OPENING ARRAYFILE' and an abend.

### 4000-VBRFILE-OPEN

Opens VBRCFILE for output in variable-length mode; a non-successful status triggers display of 'ERROR OPENING VBRC FILE' and an abend.

### 9000-ACCTFILE-CLOSE

Uses arithmetic statements to set APPL-RESULT to 8, then closes ACCTFILE. If the status is '00', APPL-RESULT is zeroed via subtraction; otherwise it is set to 12 via addition. A non-zero APPL-RESULT triggers display of 'ERROR CLOSING ACCOUNT FILE' and the abend chain.

### 9999-ABEND-PROGRAM

Displays the literal 'ABENDING PROGRAM', sets TIMING to zero and ABCODE to 999, then calls CEE3ABD with both values. This Language Environment service produces a controlled abnormal termination with a user-specified abend code, generating a dump if the job class is configured for one.

### 9910-DISPLAY-IO-STATUS

Inspects IO-STATUS to determine which display path to use. If IO-STATUS is non-numeric or IO-STAT1 (its first character) equals '9', the routine decodes the status as a VSAM extended code: it moves IO-STAT1 into the first byte of IO-STATUS-04, zeros TWO-BYTES-BINARY, moves IO-STAT2 into TWO-BYTES-RIGHT (using the character alias TWO-BYTES-ALPHA), then moves the resulting TWO-BYTES-BINARY integer value into IO-STATUS-0403 (the three-digit subfield of IO-STATUS-04), and displays the formatted result. Otherwise it moves the literal '0000' to IO-STATUS-04, overlays the last two characters with IO-STATUS, and displays the result.

## Business Rules Surfaced

- **BR-001** — The read loop is governed by a flag that must equal 'N' to continue iterating; setting it to 'Y' on end-of-file is the only normal exit path from the loop.
- **BR-002** — Only records obtained with a successful file status trigger any downstream output processing; failed reads produce no output records.
- **BR-003** — A file-status value of '10' is the sole condition that maps to a normal end-of-file result; all other non-zero values are treated as errors requiring immediate abend.
- **BR-004** — When a source account record carries a zero current-cycle debit, the output record receives an injected default value of 2525.00 rather than zero.
- **BR-005** — A failure to open ACCTFILE is immediately fatal; the program cannot proceed without its primary input.
- **BR-006** — A failure to open OUTFILE is immediately fatal.
- **BR-007** — A failure to open ARRYFILE is immediately fatal.
- **BR-008** — A failure to open VBRCFILE is immediately fatal.
- **BR-009** — Each write to OUTFILE is individually validated; a write error is fatal.
- **BR-010** — Each write to ARRYFILE is individually validated; a write error is fatal.
- **BR-011** — Each short-record write to VBRCFILE is individually validated; a write error is fatal.
- **BR-012** — Each long-record write to VBRCFILE is individually validated; a write error is fatal.
- **BR-013** — The I/O status display routine has two code paths: standard numeric status codes are displayed as-is, while non-numeric or VSAM extended codes ('9x') are decoded by overlaying binary and character views of the same two bytes.
- **BR-014** — Every account record read from the input file is echoed to standard output in full before any transformation or write operation, providing a complete per-record audit trail.
- **BR-015** — Failure to close ACCTFILE is treated as fatal, preventing silent data loss or file corruption at job end.

## Graph Summary

- **CALLS (static):** CBACT01C → COBDATFT (date formatting, unconditional, once per record in 1300-POPUL-ACCT-RECORD)
- **CALLS (static):** CBACT01C → CEE3ABD (controlled abend, conditional on any I/O failure, in 9999-ABEND-PROGRAM)
- **COPYBOOKS:** CBACT01C uses CVACT01Y (account record layout, app/cpy) and CODATECN (date conversion communication record, app/cpy)
- **VSAM READ:** CBACT01C reads ACCTFILE (INDEXED, sequential access, key FD-ACCT-ID)
- **SEQUENTIAL WRITE:** CBACT01C writes OUTFILE (flat expanded account record, one record per ACCTFILE input)
- **SEQUENTIAL WRITE:** CBACT01C writes ARRYFILE (balance array record, one record per ACCTFILE input)
- **SEQUENTIAL WRITE (variable-length):** CBACT01C writes VBRCFILE (two records per ACCTFILE input: 12-byte short and 39-byte long variants)
- **REDEFINES (2):** TWO-BYTES-ALPHA/TWO-BYTES-BINARY (binary-vs-character dual-view for VSAM status decoding); WS-REISSUE-DATE/WS-ACCT-REISSUE-DATE (flat-vs-structured dual-view for reissue date handling)
- **RULES (active):** BR-001 through BR-015, all reachable
- **DEAD CODE PARAGRAPHS (CFG artefacts):** GOBACK, WS-REISSUE-DATE, END-IF, VB2-ACCT-ID — all marked unreachable by Phase 0 static analysis; three of these are misidentified data items or scope terminators, not true paragraphs
- **GOTO FLAGS:** No GOTO statements present in source; all goto_targets arrays are empty; no irreducible GOTOs flagged by Cobol-REKT
