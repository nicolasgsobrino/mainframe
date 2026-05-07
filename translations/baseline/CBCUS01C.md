---
schema_version: "cobol-md/1.0"
program_id: "CBCUS01C"
source_file: "app/cbl/CBCUS01C.cbl"
source_sha: "88a99d7fc534579e538c438a4860e72ec068730c"
translation_date: "2026-04-23"
translating_agent: "claude-opus-4-5 (subagent)"
aifirst_task_id: "T-2026-04-23-001"
cfg_source: "validation/structure/CBCUS01C_cfg.json"

business_domain: "Customer Management"
subtype: "Batch"

author: "AWS"
date_written: null
lines_of_code: 120
divisions:
  identification: true
  environment: true
  data: true
  procedure: true
environment:
  compiler: "IBM Enterprise COBOL"
  target: "Batch/VSAM"
  runtime: "z/OS"

calls_to:
  - program: "CEE3ABD"
    condition: "APPL-RESULT is neither zero nor sixteen after a file operation fails"
    call_type: "STATIC"

called_by: []

copybooks_used:
  - name: "CVCUS01Y"
    path: "app/cpy/CVCUS01Y.cpy"
    sha: null

file_control:
  - ddname: "CUSTFILE"
    organization: "INDEXED"
    access: "SEQUENTIAL"
    record_key: "FD-CUST-ID"
    crud: ["READ"]

cics_commands: []
transaction_ids: []

data_items:
  - name: "FD-CUSTFILE-REC"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "File Description record group for CUSTFILE; the top-level container for the raw 500-byte customer record read from the VSAM KSDS, comprising a nine-digit customer ID and a 491-byte data payload."

  - name: "CUSTFILE-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character VSAM file-status code for CUSTFILE; the first byte carries the primary status class and the second byte carries the secondary status detail; tested after every OPEN, READ, and CLOSE."

  - name: "IO-STATUS"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character general-purpose I/O status staging area; populated by copying CUSTFILE-STATUS into it before passing control to the display and abend error handlers."

  - name: "TWO-BYTES-BINARY"
    level: 01
    picture: "9(4)"
    usage: "BINARY"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Four-digit unsigned binary integer occupying two bytes; used as the numeric operand in the I/O-status display helper to convert a single-byte character status code into a three-digit printable decimal."

  - name: "TWO-BYTES-ALPHA"
    level: 01
    picture: null
    usage: "BINARY"
    value: null
    redefines: "TWO-BYTES-BINARY"
    redefines_interpretations:
      - condition: "IO-STAT1 = '9' or IO-STATUS is NOT NUMERIC — the non-numeric I/O status path is active"
        interpreted_as: "Two individual single-character fields (TWO-BYTES-LEFT and TWO-BYTES-RIGHT) overlaying the same two bytes; TWO-BYTES-RIGHT receives the raw second status byte so that TWO-BYTES-BINARY can be read back as a numeric value for display"
        encoding: "DISPLAY"
      - condition: "IO-STATUS is NUMERIC and IO-STAT1 is not '9' — the numeric I/O status path is active"
        interpreted_as: "The same two bytes treated as a four-digit unsigned binary integer; the field is zeroed and only TWO-BYTES-BINARY is used directly, so the alpha overlay is dormant and the storage is interpreted purely as a binary number"
        encoding: "BINARY"
    dead_code_flag: false
    semantic: "Character overlay of TWO-BYTES-BINARY; exposes the two bytes as left and right single-character subfields so the I/O-status display routine can move an individual status byte into the high or low byte of the binary integer without arithmetic conversion."

  - name: "IO-STATUS-04"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Four-character formatted I/O status display group; assembled at runtime into a human-readable four-character string and passed to DISPLAY so operators can read the file status code in the job log."

  - name: "APPL-RESULT"
    level: 01
    picture: "S9(9)"
    usage: "COMP"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Signed nine-digit binary integer used as a return-code accumulator; set to 0 on success, 16 on end-of-file, 12 on unexpected error, and 8 as a sentinel before each file operation; condition-name APPL-AOK tests for zero and APPL-EOF tests for sixteen."

  - name: "END-OF-FILE"
    level: 01
    picture: "X(01)"
    usage: null
    value: "N"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Single-character end-of-file flag initialised to 'N'; set to 'Y' when a sequential READ returns the end-of-file status code, which terminates the main processing loop."

  - name: "ABCODE"
    level: 01
    picture: "S9(9)"
    usage: "BINARY"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Signed nine-digit binary integer holding the abend code passed to the Language Environment abnormal-termination service CEE3ABD; set to 999 before the call to force a user abend."

  - name: "TIMING"
    level: 01
    picture: "S9(9)"
    usage: "BINARY"
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Signed nine-digit binary integer holding the timing option passed to CEE3ABD; set to 0 to request immediate abend without a timing delay."

procedure_paragraphs:
  - name: "END-PERFORM"
    reachable: true
    performs:
      - "0000-CUSTFILE-OPEN"
      - "1000-CUSTFILE-GET-NEXT"
      - "9000-CUSTFILE-CLOSE"
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Main inline control block that announces program start, opens the customer file, loops sequentially through all records displaying each one, closes the file, and returns to the caller."

  - name: "GOBACK"
    reachable: false
    performs:
      - "0000-CUSTFILE-OPEN"
      - "1000-CUSTFILE-GET-NEXT"
      - "9000-CUSTFILE-CLOSE"
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Static-analysis artifact representing the GOBACK statement that terminates program execution; marked unreachable by the CFG tool because it is structurally subsumed by the END-PERFORM node in the extracted control-flow graph."

  - name: "1000-CUSTFILE-GET-NEXT"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Reads the next sequential record from CUSTFILE into the CUSTOMER-RECORD working-storage area, sets APPL-RESULT to reflect success, end-of-file, or error, and either continues, sets the end-of-file flag, or invokes the error-display and abend handlers."

  - name: "0000-CUSTFILE-OPEN"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Opens CUSTFILE for sequential input, checks the file status, sets APPL-RESULT to zero on success or twelve on failure, and abends the program if the open did not succeed."

  - name: "9000-CUSTFILE-CLOSE"
    reachable: true
    performs:
      - "Z-DISPLAY-IO-STATUS"
      - "Z-ABEND-PROGRAM"
    goto_targets: []
    summary: "Closes CUSTFILE, checks the file status, resets APPL-RESULT to zero on success or twelve on failure, and abends the program if the close did not succeed."

  - name: "Z-ABEND-PROGRAM"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Sets TIMING to zero and ABCODE to 999, then calls the IBM Language Environment abnormal-termination service CEE3ABD to force an immediate user abend with abend code 999."

  - name: "Z-DISPLAY-IO-STATUS"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Formats the two-byte I/O status code into a four-character printable string and displays it on the operator console, using the TWO-BYTES-BINARY/TWO-BYTES-ALPHA overlay pair to convert a non-numeric or physical-error status byte into a decimal integer."

business_rules:
  - id: "BR-001"
    rule: "The customer file must open with status '00'; any other status causes an immediate program abend via CEE3ABD."
    source_paragraph: "0000-CUSTFILE-OPEN"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-002"
    rule: "A sequential read returning status '00' is treated as a successful record retrieval and the customer record is displayed; status '10' signals normal end-of-file and is mapped to APPL-RESULT value 16; any other status is treated as an unrecoverable error."
    source_paragraph: "1000-CUSTFILE-GET-NEXT"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-003"
    rule: "When APPL-RESULT equals 16 (end-of-file condition), the END-OF-FILE flag is set to 'Y', which terminates the main processing loop without an abend."
    source_paragraph: "1000-CUSTFILE-GET-NEXT"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-004"
    rule: "When APPL-RESULT is neither zero nor sixteen after a read attempt, the program displays an error message, formats the file status for the operator, and abends unconditionally — no retry or skip logic exists."
    source_paragraph: "1000-CUSTFILE-GET-NEXT"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-005"
    rule: "The customer file must close with status '00'; any other close status causes an immediate program abend via CEE3ABD."
    source_paragraph: "9000-CUSTFILE-CLOSE"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-006"
    rule: "When the I/O status is non-numeric or the first status byte is '9' (indicating a physical or hardware error), the status is formatted using the TWO-BYTES-BINARY overlay to produce a numeric representation of the second status byte; otherwise the status is displayed directly as a four-character code."
    source_paragraph: "Z-DISPLAY-IO-STATUS"
    rule_type: "transform"
    confidence: "high"
    reachable: true

  - id: "BR-007"
    rule: "Each successfully read customer record is displayed immediately to the operator console inside the read loop, making the program a sequential audit-print utility rather than a transforming batch job."
    source_paragraph: "END-PERFORM"
    rule_type: "display"
    confidence: "high"
    reachable: true

validation:
  t01_schema_valid: null
  t02_structural_complete: null
  t02r_redefines_complete: null
  t03_functional_score: null
  t04_semantic_score: null
  t05_regression_pass: null
  overall: "PENDING"
---

# CBCUS01C — Sequential Customer File Print Utility

## Purpose

CBCUS01C is a batch utility program in the CardDemo application that performs a full sequential scan of the customer VSAM KSDS file and prints every customer record to the operator console. It serves as a diagnostic and audit tool: it opens the file, reads records one at a time until end-of-file is reached, displays each record, then closes the file and exits. No transformation, filtering, or update logic is performed; the program's sole output channel is the system console display.

## Runtime Context

The program runs as a standard IBM z/OS batch job step. It requires no CICS infrastructure and issues no EXEC CICS commands. A single VSAM KSDS data set is assigned to the DD name CUSTFILE; the file is opened in sequential (read-only) input mode and traversed from first record to last. On any file-operation failure the program calls the IBM Language Environment service CEE3ABD to force an abnormal termination with abend code 999, ensuring that job-step completion codes are non-zero and upstream schedulers can detect the failure. The customer record layout is brought in through the CVCUS01Y copybook, which defines a 500-byte record containing customer identity, address, contact, and credit-score fields.

## Data Layout

**File Description area.** The raw file record is modelled as a two-field group: a nine-digit numeric customer identifier followed by a 491-byte character data payload. When a record is read with the INTO phrase, the file-description buffer is bypassed and the data is moved directly into the CUSTOMER-RECORD working-storage group defined by the CVCUS01Y copybook.

**CUSTOMER-RECORD (from CVCUS01Y).** This 500-byte group is the primary data structure. It contains the nine-digit customer ID, three 25-character name fields (first, middle, last), three 50-character address lines, a two-character state code, a three-character country code, a ten-character postal code, two 15-character phone numbers, a nine-digit Social Security Number, a 20-character government-issued ID, a ten-character date-of-birth in YYYY-MM-DD format, a ten-character EFT account identifier, a one-character primary card-holder indicator, a three-digit FICO credit score, and a 168-byte filler pad that rounds the record to 500 bytes.

**CUSTFILE-STATUS / IO-STATUS.** Both are two-character group items, each composed of a left and a right single-character subfield. CUSTFILE-STATUS is updated automatically by the runtime after each file operation. IO-STATUS is a staging copy used exclusively within the error-reporting and abend path.

**TWO-BYTES-BINARY / TWO-BYTES-ALPHA — REDEFINES pair.** These two 01-level items share the same two bytes of storage. TWO-BYTES-BINARY declares the storage as a four-digit unsigned binary integer (BINARY usage). TWO-BYTES-ALPHA redefines that same memory as a group of two single-character fields named TWO-BYTES-LEFT and TWO-BYTES-RIGHT. The runtime selector that determines which interpretation is active is the value of IO-STAT1 and the numeric/non-numeric nature of IO-STATUS: when the I/O error is a physical or hardware error (IO-STAT1 equals '9') or when IO-STATUS is not numeric, the program zeroes TWO-BYTES-BINARY, then moves the second status byte into TWO-BYTES-RIGHT via the alpha overlay, and finally reads TWO-BYTES-BINARY back as a decimal integer for display. In the numeric-status path the alpha subfields are not referenced and the storage behaves purely as a binary integer. This dual-interpretation technique avoids a numeric-conversion subroutine and is a common z/OS COBOL idiom for converting a single raw byte to a displayable decimal value.

**IO-STATUS-04.** A four-character group composed of a single leading digit subfield and a three-digit trailing subfield. It is assembled at runtime into a four-character printable representation of the file status code and then displayed. The same memory is also addressable as a four-byte reference-modification target.

**APPL-RESULT.** A signed nine-digit binary (COMP) integer that acts as a return-code accumulator. Two level-88 condition names are defined on it: APPL-AOK is true when the value is zero (operation succeeded) and APPL-EOF is true when the value is sixteen (end-of-file reached). The value 12 is used for unrecoverable errors and 8 is loaded as a sentinel before each file operation.

**END-OF-FILE.** A single-character flag initialised to 'N'; it is set to 'Y' only when end-of-file is confirmed, which causes the outer PERFORM loop to exit normally.

**ABCODE and TIMING.** Two signed nine-digit binary fields used exclusively in the abend handler: ABCODE receives the value 999 and TIMING receives zero before CEE3ABD is called.

## Procedure Logic

### END-PERFORM (main inline control flow)

This is the program's top-level control node as identified by the CFG tool. It represents the inline code in the Procedure Division that executes before any named paragraph. Execution begins by displaying a start-of-program banner to the console. It then calls the file-open paragraph, enters a PERFORM UNTIL loop that iterates as long as the end-of-file flag is 'N', and within each iteration calls the record-read paragraph and, if the flag is still 'N' after the read, displays the customer record. When the loop exits, it calls the file-close paragraph, displays an end-of-program banner, and issues GOBACK to return control to the job scheduler.

### GOBACK

This node is marked unreachable by static analysis and represents the GOBACK statement as a discrete CFG endpoint. In the source it is the final statement of the inline main-block and is always reached at runtime; the CFG tool's reachability classification reflects a graph-traversal artifact rather than genuine dead code. The GOBACK statement terminates the program and returns to the calling environment.

### 1000-CUSTFILE-GET-NEXT

This paragraph performs a single sequential READ of CUSTFILE, directing the record into the CUSTOMER-RECORD working-storage area. It examines CUSTFILE-STATUS immediately after the read: status '00' indicates success and sets APPL-RESULT to zero; status '10' indicates end-of-file and sets APPL-RESULT to sixteen; any other status sets APPL-RESULT to twelve. A second conditional then tests the condition names: if APPL-AOK is true execution continues normally; if APPL-EOF is true the end-of-file flag is set to 'Y'; otherwise an error message is displayed, IO-STATUS is loaded from CUSTFILE-STATUS, and the status-display and abend paragraphs are invoked.

### 0000-CUSTFILE-OPEN

This paragraph loads the sentinel value eight into APPL-RESULT, issues an OPEN INPUT for CUSTFILE, then inspects CUSTFILE-STATUS: status '00' resets APPL-RESULT to zero; any other status sets it to twelve. If APPL-AOK is not true, the paragraph displays an error message, copies the status into IO-STATUS, and delegates to the status-display and abend paragraphs.

### 9000-CUSTFILE-CLOSE

This paragraph uses arithmetic expressions to load the sentinel value eight into APPL-RESULT, issues a CLOSE for CUSTFILE, then inspects CUSTFILE-STATUS using the same success/failure logic as the open paragraph. On failure it displays an error message, copies the status, and calls the error and abend helpers. The use of arithmetic (ADD 8 TO ZERO GIVING and SUBTRACT from self) to set and clear APPL-RESULT is functionally equivalent to simple MOVE statements but is a defensive coding pattern sometimes used to suppress optimizer side-effects.

### Z-ABEND-PROGRAM

This paragraph sets TIMING to zero and ABCODE to 999, then calls the IBM Language Environment abnormal-termination routine CEE3ABD with those two values as parameters, causing the job step to abend with a user abend code of 999 and producing a diagnostic dump for problem analysis.

### Z-DISPLAY-IO-STATUS

This paragraph formats the two-byte IO-STATUS value into a four-character printable string for console display. If IO-STATUS is non-numeric or if the first status byte is '9' (signalling a physical I/O error), it moves the first byte directly into the first position of IO-STATUS-04, zeroes TWO-BYTES-BINARY, moves the second byte into TWO-BYTES-RIGHT via the character overlay, reads the resulting numeric value from TWO-BYTES-BINARY into the three-digit trailing subfield of IO-STATUS-04, and displays the assembled string. For normal numeric status codes it blanks IO-STATUS-04, overlays the last two characters with the status string using reference modification, and displays the result.

## Business Rules Surfaced

**BR-001 — File-open guard.** The customer file must open successfully (status '00'); any failure triggers an immediate abend. There is no retry or alternative open path.

**BR-002 — Read-status classification.** A read status of '00' is the only success indicator; '10' is the sole end-of-file signal; all other codes are fatal errors. This three-way classification means any VSAM exceptional-status code outside '00' and '10' will halt the job.

**BR-003 — End-of-file loop termination.** When the end-of-file result code (16) is set, the END-OF-FILE flag transitions from 'N' to 'Y', which is the only mechanism by which the main read loop exits cleanly.

**BR-004 — No error recovery.** When a read error is not end-of-file, the program neither skips the record nor retries; it displays diagnostics and abends unconditionally. This is a zero-tolerance error policy for unexpected VSAM conditions.

**BR-005 — File-close guard.** The customer file must close successfully; failure causes an abend on the way out, ensuring that the operator is notified even if all records were processed correctly.

**BR-006 — Physical-error status formatting.** When the first status byte is '9' or the status is non-numeric, a byte-level conversion via the TWO-BYTES-BINARY/TWO-BYTES-ALPHA overlay is used to render the second status byte as a decimal number, providing the operator with a meaningful numeric error code rather than a raw binary byte.

**BR-007 — Full-file display policy.** Every successfully read customer record is displayed to the console; there is no filtering predicate, no sampling, and no record count limit, so the program will display the entire contents of the customer file on each execution.

## Graph Summary

- **CALLS:** CBCUS01C -[:CALLS {condition: "APPL-RESULT is not 0 or 16 after file operation failure", call_type: "STATIC"}]-> CEE3ABD
- **COPYBOOKS:** CBCUS01C -[:USES_COPYBOOK]-> CVCUS01Y (app/cpy/CVCUS01Y.cpy) — provides the 500-byte CUSTOMER-RECORD group structure
- **VSAM READS:** CBCUS01C -[:READS]-> CUSTFILE (INDEXED, SEQUENTIAL access, key FD-CUST-ID)
- **PARAGRAPHS (reachable):** END-PERFORM, 1000-CUSTFILE-GET-NEXT, 0000-CUSTFILE-OPEN, 9000-CUSTFILE-CLOSE, Z-ABEND-PROGRAM, Z-DISPLAY-IO-STATUS
- **PARAGRAPHS (unreachable/CFG artifact):** GOBACK
- **REDEFINES:** TWO-BYTES-ALPHA redefines TWO-BYTES-BINARY — two interpretations gated by IO-STAT1 value and numeric status test
- **BUSINESS RULES:** 7 rules surfaced (BR-001 through BR-007); all reachable; types: 5 guard, 1 transform, 1 display
- **DEAD CODE:** No data items flagged dead; GOBACK paragraph flagged unreachable by CFG static analysis (likely a graph-extraction artifact — the statement executes at runtime)
