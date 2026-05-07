---
schema_version: "cobol-md/1.0"
program_id: "COSGN00C"
source_file: "app/cbl/COSGN00C.cbl"
source_sha: "c3e7f8e4fb96466d3822ad82ceda8a96fb555d78"
translation_date: "2026-04-23"
translating_agent: "claude-opus-4-5 (subagent)"
aifirst_task_id: "T-2026-04-23-001"
cfg_source: "validation/structure/COSGN00C_cfg.json"

business_domain: "Administration"
subtype: "CICS-Online"

author: "AWS"
date_written: null
lines_of_code: 197
divisions:
  identification: true
  environment: true
  data: true
  procedure: true
environment:
  compiler: "IBM Enterprise COBOL"
  target: "CICS/VSAM"
  runtime: "z/OS"

calls_to:
  - program: "COADM01C"
    condition: "CDEMO-USRTYP-ADMIN is true (user type flag indicates administrator)"
    call_type: "EXEC CICS XCTL"
  - program: "COMEN01C"
    condition: "CDEMO-USRTYP-ADMIN is false (user type flag indicates regular user)"
    call_type: "EXEC CICS XCTL"

called_by:
  - "CC00 (CICS transaction initiator)"

copybooks_used:
  - name: "COCOM01Y"
    path: "app/cpy/COCOM01Y.cpy"
    sha: null
  - name: "COSGN00"
    path: "app/cpy-bms/COSGN00.CPY"
    sha: null
  - name: "COTTL01Y"
    path: "app/cpy/COTTL01Y.cpy"
    sha: null
  - name: "CSDAT01Y"
    path: "app/cpy/CSDAT01Y.cpy"
    sha: null
  - name: "CSMSG01Y"
    path: "app/cpy/CSMSG01Y.cpy"
    sha: null
  - name: "CSUSR01Y"
    path: "app/cpy/CSUSR01Y.cpy"
    sha: null
  - name: "DFHAID"
    path: "app/cpy-stubs/DFHAID.cpy"
    sha: null
  - name: "DFHBMSCA"
    path: "app/cpy-stubs/DFHBMSCA.cpy"
    sha: null

file_control:
  - ddname: "USRSEC"
    organization: "INDEXED"
    access: "RANDOM"
    record_key: "WS-USER-ID"
    crud: ["READ"]

cics_commands:
  - "RETURN"
  - "RECEIVE"
  - "SEND"
  - "ASSIGN"
  - "READ"
  - "XCTL"

transaction_ids:
  - "CC00"

data_items:
  - name: "WS-VARIABLES"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Top-level working-storage group holding all program-local variables including program name, transaction ID, message buffer, file name, error flag, response codes, and user credential fields"

  - name: "DFHCOMMAREA"
    level: 01
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "CICS Communication Area passed into this program from the transaction invocation; contains the variable-length linkage area whose actual size is determined by the CICS-managed EIBCALEN field at runtime"

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
    goto_targets: []
    summary: "Entry point for transaction CC00; resets error state, then branches based on whether a commarea exists (first invocation shows the screen) and which AID key was pressed (Enter processes credentials, PF3 displays a thank-you and exits, any other key shows an invalid-key error), before issuing a CICS RETURN to re-invoke the same transaction with the commarea."

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
    goto_targets: []
    summary: "Unreachable paragraph artifact produced by the CFG tool from an inline END-IF delimiter; contains no independent logic and is flagged as dead code by static analysis."

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
    goto_targets: []
    summary: "Unreachable paragraph artifact produced by the CFG tool from an inline END-EXEC delimiter; contains no independent logic and is flagged as dead code by static analysis."

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
    goto_targets: []
    summary: "Receives the BMS map from the terminal, validates that neither the user ID nor password field is blank (re-displaying the sign-on screen with an error message if either is empty), then uppercases both fields and invokes READ-USER-SEC-FILE when no error flag is set."

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
    goto_targets: []
    summary: "Unreachable paragraph artifact produced by the CFG tool from an inline END-EVALUATE delimiter; contains no independent logic and is flagged as dead code by static analysis."

  - name: "SEND-SIGNON-SCREEN"
    reachable: true
    performs:
      - "POPULATE-HEADER-INFO"
    goto_targets: []
    summary: "Populates the BMS output map header fields, copies the current message to the error-message area of the map, and issues a CICS SEND to display the sign-on screen (COSGN0A in mapset COSGN00) with cursor positioning and screen erase."

  - name: "SEND-PLAIN-TEXT"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Sends a plain-text message string directly to the terminal (used for the PF3 thank-you farewell message) and then issues an unconditional CICS RETURN with no TRANSID, ending the conversation."

  - name: "POPULATE-HEADER-INFO"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Obtains the current date and time via FUNCTION CURRENT-DATE, formats them into month/day/year and hours/minutes/seconds display strings, moves the application title lines, transaction ID, and program name into the BMS output map, and queries CICS for the APPLID and SYSID to display in the header."

  - name: "READ-USER-SEC-FILE"
    reachable: true
    performs:
      - "SEND-SIGNON-SCREEN"
    goto_targets: []
    summary: "Issues a CICS READ against the USRSEC VSAM dataset keyed on WS-USER-ID; on a successful read (response code 0) it verifies the stored password matches WS-USER-PWD and, if correct, populates the commarea with identity/role data before transferring control via XCTL to either the administrator menu (COADM01C) or the regular-user menu (COMEN01C); on response code 13 (record not found) or any other error it displays an appropriate error message."

business_rules:
  - id: "BR-001"
    rule: "If no commarea is present (EIBCALEN equals zero), the program is on its first invocation and must display the sign-on screen immediately without attempting to process any input."
    source_paragraph: "MAIN-PARA"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-002"
    rule: "Only the Enter key (DFHENTER) triggers credential processing; PF3 triggers a graceful exit with a thank-you message; any other AID key is rejected as invalid and causes an error message to be displayed on the sign-on screen."
    source_paragraph: "MAIN-PARA"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-003"
    rule: "If the user ID field on the sign-on screen is blank or contains low-values, processing is halted and the user is prompted to enter a user ID before any authentication attempt is made."
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-004"
    rule: "If the password field on the sign-on screen is blank or contains low-values, processing is halted and the user is prompted to enter a password before any authentication attempt is made."
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-005"
    rule: "Both the user ID and password values received from the terminal are uppercased before comparison and storage, ensuring that authentication is case-insensitive for the user but stored in a canonical form."
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "transform"
    confidence: "high"
    reachable: true

  - id: "BR-006"
    rule: "The user security file (USRSEC) is only read when no error flag is set; if any prior validation step raised the error flag, the file read is skipped entirely."
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-007"
    rule: "If the USRSEC record is found (response code 0) and the stored password matches the entered password, the user is authenticated; a mismatched password results in a 'Wrong Password' error message without distinguishing which field was wrong."
    source_paragraph: "READ-USER-SEC-FILE"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-008"
    rule: "Authenticated users whose user-type flag indicates administrator status (CDEMO-USRTYP-ADMIN) are routed to the administration menu program (COADM01C) via XCTL; all other authenticated users are routed to the standard main menu program (COMEN01C)."
    source_paragraph: "READ-USER-SEC-FILE"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-009"
    rule: "If the USRSEC READ returns response code 13 (record not found), the user is told their user ID was not found and is prompted to try again; the error flag is set to suppress further processing in the current cycle."
    source_paragraph: "READ-USER-SEC-FILE"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-010"
    rule: "Any USRSEC READ response code other than 0 or 13 triggers a generic 'Unable to verify the User' error message, masking the underlying system error from the end user while still preventing sign-on."
    source_paragraph: "READ-USER-SEC-FILE"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-011"
    rule: "Upon successful authentication the commarea is populated with the originating transaction ID, program name, user ID, and user type before control is transferred, ensuring downstream programs receive a fully initialized session context."
    source_paragraph: "READ-USER-SEC-FILE"
    rule_type: "audit"
    confidence: "high"
    reachable: true

  - id: "BR-012"
    rule: "The CICS RETURN at the end of MAIN-PARA always specifies TRANSID 'CC00' and passes the CARDDEMO-COMMAREA, so if control returns without a successful XCTL the sign-on screen will be re-presented on the next keystroke."
    source_paragraph: "MAIN-PARA"
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

bms_maps:
  - map: "COSGN0A"
    translation_status: pending-extraction
    note: "CICS BMS screen map — structural fields not yet extracted into MD schema"
---

# COSGN00C — CardDemo Application Sign-On Screen

## Purpose

COSGN00C is the interactive sign-on gateway for the CardDemo CICS application. It presents a BMS-based credential screen to the end user, validates the supplied user ID and password against a VSAM security file (USRSEC), and—upon successful authentication—transfers control to either the administrator menu or the standard main menu depending on the user's stored role type. It enforces input presence rules, case-normalization of credentials, and provides distinct error messages for each failure mode without leaking internal system details to the terminal user.

## Runtime Context

This program runs under CICS transaction identifier **CC00** on z/OS. It is a pseudo-conversational program: each user interaction causes a CICS RETURN with TRANSID CC00 and a commarea, so the next terminal input re-invokes the same program. The program uses the BMS map COSGN0A within mapset COSGN00 for all screen I/O (RECEIVE to read input, SEND to display output). It reads the USRSEC VSAM indexed dataset keyed on user ID to perform credential lookup. On successful login it issues an EXEC CICS XCTL—a non-returning transfer of control—to either COADM01C (administrator path) or COMEN01C (regular-user path), passing the populated commarea. No file writes or deletes are performed; the only file operation is a single VSAM READ. The DFHCOMMAREA linkage area conveys session state between invocations; EIBCALEN and EIBAID from the Execute Interface Block govern first-invocation detection and AID-key routing respectively.

## Data Layout

### Program Variables (WS-VARIABLES group)

The primary working-storage group bundles all local program state into a single 01-level container. Within it, an eight-character field holds the literal program name "COSGN00C" used to stamp the header display and the commarea's originating-program field. A four-character field holds the transaction identifier "CC00" used both in the screen header and in the CICS RETURN TRANSID clause. An eighty-character message buffer accumulates the human-readable status or error text that is written to the BMS map's error-message output field before each SEND. An eight-character field holds the VSAM dataset name "USRSEC  " (with trailing spaces) used as the CICS READ DATASET argument. A single-character error-flag field is governed by two condition-name (level-88) aliases: ERR-FLG-ON (value "Y") and ERR-FLG-OFF (value "N"), providing readable boolean semantics for setting and testing the flag throughout the procedure. Two binary (COMP) signed nine-digit numeric fields capture the primary and secondary CICS response codes returned by each EXEC CICS command. Two eight-character fields hold the uppercased user ID and password collected from the terminal; WS-USER-ID doubles as the VSAM key for the READ operation.

### Linkage Section (DFHCOMMAREA)

The DFHCOMMAREA group in the Linkage Section provides access to the CICS-supplied communication area. Its sole subordinate field is a one-character element that occurs between 1 and 32,767 times depending on the value of EIBCALEN, giving the program a variable-length view of the commarea byte array. In practice, the program overlays this with the typed CARDDEMO-COMMAREA structure defined in the COCOM01Y copybook, which carries the canonical commarea fields (user ID, user type, transaction ID, program name, context flags) shared across all CardDemo programs.

### Copybook-Contributed Structures

The COCOM01Y copybook provides the CARDDEMO-COMMAREA group, which includes CDEMO-USER-ID, CDEMO-USER-TYPE, CDEMO-FROM-TRANID, CDEMO-FROM-PROGRAM, CDEMO-PGM-CONTEXT, and the condition name CDEMO-USRTYP-ADMIN that tests whether the user-type byte indicates administrator access. The COSGN00 BMS copybook supplies the COSGN0AI (input) and COSGN0AO (output) map structures for screen fields including USERIDI/USERIDL, PASSWDI/PASSWDL, ERRMSGO, TITLE01O, TITLE02O, TRNNAMEO, PGMNAMEO, CURDATEO, CURTIMEO, APPLIDO, and SYSIDO. The COTTL01Y copybook provides the application title constants CCDA-TITLE01 and CCDA-TITLE02. The CSDAT01Y copybook provides the current-date working-storage group including WS-CURDATE-DATA, WS-CURDATE-MONTH, WS-CURDATE-DAY, WS-CURDATE-YEAR, WS-CURDATE-MM, WS-CURDATE-DD, WS-CURDATE-YY, WS-CURDATE-MM-DD-YY, and the parallel time fields for hours, minutes, seconds, and formatted time string. The CSMSG01Y copybook provides CCDA-MSG-THANK-YOU (the PF3 farewell text) and CCDA-MSG-INVALID-KEY (the invalid-AID error text). The CSUSR01Y copybook provides the SEC-USER-DATA group and its SEC-USR-PWD and SEC-USR-TYPE sub-fields used to interpret the VSAM user security record. DFHAID provides the CICS AID-key symbolic constants (DFHENTER, DFHPF3, etc.). DFHBMSCA provides BMS attribute byte constants used in map field control.

No REDEFINES clauses are declared in the program's own data division; the CFG redefines_clauses array is empty, so no redefines_interpretations entries are required.

## Procedure Logic

### MAIN-PARA

MAIN-PARA is the program's sole entry point, always reached first when transaction CC00 fires. It begins by clearing the error flag to its "off" state and blanking both the working-storage message buffer and the BMS output map's error-message field. It then tests the CICS Execute Interface Block field EIBCALEN: if it equals zero the program is being invoked for the first time in this pseudo-conversation (no commarea yet exists), so it clears the BMS output map to low-values, positions the cursor on the user-ID input field, and calls SEND-SIGNON-SCREEN to present a blank sign-on form. If EIBCALEN is non-zero a commarea exists and the program switches on EIBAID to determine which attention key the user pressed. An Enter key routes to PROCESS-ENTER-KEY for credential handling. PF3 moves the configured thank-you message into the message buffer and calls SEND-PLAIN-TEXT to display it and end the conversation. Any other AID key sets the error flag and moves the invalid-key message into the buffer before calling SEND-SIGNON-SCREEN to re-display the form with the error. After all branches, MAIN-PARA issues a CICS RETURN specifying TRANSID "CC00" and the CARDDEMO-COMMAREA so that the next terminal event re-invokes this program.

### END-IF

This entry is a CFG tool artifact representing the END-IF delimiter of the conditional block in MAIN-PARA; it is marked unreachable by static analysis and carries no independent business logic.

### END-EXEC

This entry is a CFG tool artifact representing an END-EXEC delimiter; it is marked unreachable by static analysis and carries no independent business logic.

### PROCESS-ENTER-KEY

Called when the user presses Enter with a commarea present. It first issues a CICS RECEIVE to read the terminal input into the COSGN0AI map structure, capturing the CICS primary and secondary response codes. It then evaluates the input fields in priority order: if the user-ID input field is blank or contains low-values, the error flag is set and the cursor is moved to the user-ID field before SEND-SIGNON-SCREEN is called with a "Please enter User ID" message; if instead the password input field is blank or contains low-values, the same pattern is applied with a "Please enter Password" message targeting the password field; otherwise, processing continues. After the evaluation, both the user-ID and password values are converted to uppercase via FUNCTION UPPER-CASE and stored in WS-USER-ID, CDEMO-USER-ID, and WS-USER-PWD respectively. Finally, if the error flag is still in the "off" state, READ-USER-SEC-FILE is performed to attempt authentication.

### END-EVALUATE

This entry is a CFG tool artifact representing an END-EVALUATE delimiter in PROCESS-ENTER-KEY; it is marked unreachable by static analysis and carries no independent business logic.

### SEND-SIGNON-SCREEN

Invoked from multiple points whenever the sign-on form must be displayed or re-displayed. It first calls POPULATE-HEADER-INFO to ensure the date, time, application ID, and system ID are current in the output map. It then copies the current working-storage message buffer content into the ERRMSGO field of the BMS output map. Finally, it issues a CICS SEND MAP command for map COSGN0A in mapset COSGN00, specifying the output map structure, ERASE (to clear the terminal screen before writing), and CURSOR (to position the cursor at the field previously assigned a cursor-position value of -1).

### SEND-PLAIN-TEXT

Invoked exclusively on the PF3 path. It issues a CICS SEND TEXT command to write the contents of the working-storage message buffer as raw text to the terminal, with ERASE to clear the screen and FREEKB to unlock the terminal keyboard. It then issues an unconditional CICS RETURN (with no TRANSID) to terminate the task, ending the pseudo-conversation entirely rather than re-queuing transaction CC00.

### POPULATE-HEADER-INFO

Called at the start of every SEND-SIGNON-SCREEN invocation to keep the header current. It invokes FUNCTION CURRENT-DATE to obtain the system date and time, then distributes month, day, and two-digit year into display sub-fields and assembles them into the formatted date output field. It performs the parallel operation for the current time, extracting hours, minutes, and seconds into the formatted time output field. It moves the application title lines from the COTTL01Y constants, the transaction ID from WS-TRANID, and the program name from WS-PGMNAME into their respective map output fields. It then issues two CICS ASSIGN commands: one to retrieve the CICS APPLID (application identifier) and a second to retrieve the SYSID (system identifier), storing each in the corresponding BMS output map field for display in the screen header.

### READ-USER-SEC-FILE

Called from PROCESS-ENTER-KEY after all input validations pass and the error flag is clear. It issues a CICS READ against dataset "USRSEC  " using WS-USER-ID as the key, reading the result directly into the SEC-USER-DATA copybook structure. The CICS primary response code is examined in an EVALUATE block. When the response is zero (successful read), the program compares the SEC-USR-PWD field from the VSAM record against WS-USER-PWD: if they match, the commarea is populated with WS-TRANID (from-tranid), WS-PGMNAME (from-program), WS-USER-ID (user-id), SEC-USR-TYPE (user-type), and a zero program-context value, then control is transferred via CICS XCTL to COADM01C if the user-type satisfies CDEMO-USRTYP-ADMIN or to COMEN01C otherwise; if the passwords do not match, a "Wrong Password" message is placed in the buffer and SEND-SIGNON-SCREEN is called with the cursor on the password field. When the response is 13 (record not found), the error flag is set and a "User not found" message causes SEND-SIGNON-SCREEN to be called with the cursor on the user-ID field. Any other response code also sets the error flag and calls SEND-SIGNON-SCREEN with a generic verification-failure message.

## Business Rules Surfaced

**BR-001** — If no commarea is present (first invocation), the program displays the sign-on screen immediately without attempting any input processing.

**BR-002** — Only the Enter key triggers credential processing; PF3 exits gracefully with a thank-you message; all other AID keys produce an invalid-key error on the sign-on screen.

**BR-003** — A blank or low-value user ID field stops processing and prompts the user to supply a user ID before authentication is attempted.

**BR-004** — A blank or low-value password field stops processing and prompts the user to supply a password before authentication is attempted.

**BR-005** — User ID and password values received from the terminal are uppercased before comparison and commarea storage, making authentication effectively case-insensitive.

**BR-006** — The VSAM security file is only read if no error flag was raised during input validation; validation errors prevent the file access entirely.

**BR-007** — A successful VSAM read (response 0) requires an exact password match against the stored record; a mismatch produces a "Wrong Password" error without indicating which field was incorrect.

**BR-008** — Authenticated users flagged as administrators (per the user-type byte in the security record) are routed to the administration program COADM01C; all other authenticated users are routed to the main menu program COMEN01C.

**BR-009** — A VSAM response code of 13 (record not found) produces a "User not found" error, distinguishing a missing user from a wrong password at the message level.

**BR-010** — Any VSAM response code other than 0 or 13 produces a generic "Unable to verify the User" message, hiding internal system error details from the end user.

**BR-011** — On successful authentication, the commarea is fully populated with originating transaction ID, program name, user ID, user type, and a zeroed program-context value before control is transferred, establishing a trusted session context for downstream programs.

**BR-012** — The CICS RETURN at the conclusion of MAIN-PARA always specifies TRANSID CC00 and passes the commarea, ensuring the sign-on screen is re-presented on the next terminal event unless an XCTL has already transferred control away.

## Graph Summary

- **CALLS (XCTL):** COSGN00C → COADM01C (condition: CDEMO-USRTYP-ADMIN is true)
- **CALLS (XCTL):** COSGN00C → COMEN01C (condition: CDEMO-USRTYP-ADMIN is false)
- **COPYBOOK:** COSGN00C uses COCOM01Y (commarea structure / session context)
- **COPYBOOK:** COSGN00C uses COSGN00 (BMS map COSGN0A input/output fields)
- **COPYBOOK:** COSGN00C uses COTTL01Y (application title constants)
- **COPYBOOK:** COSGN00C uses CSDAT01Y (current-date and current-time working-storage fields)
- **COPYBOOK:** COSGN00C uses CSMSG01Y (thank-you and invalid-key message constants)
- **COPYBOOK:** COSGN00C uses CSUSR01Y (user security record structure SEC-USER-DATA)
- **COPYBOOK:** COSGN00C uses DFHAID (AID-key constants DFHENTER, DFHPF3)
- **COPYBOOK:** COSGN00C uses DFHBMSCA (BMS attribute byte constants)
- **VSAM READ:** COSGN00C reads USRSEC (keyed on user ID; no writes or deletes)
- **CICS COMMANDS:** RETURN (pseudo-conversational re-queue to CC00), RECEIVE (BMS map input), SEND (BMS map output and plain-text output), ASSIGN (APPLID and SYSID retrieval), READ (USRSEC security record), XCTL (non-returning transfer to admin or main menu)
- **TRANSACTION:** Services CICS transaction ID CC00
- **RULES (reachable):** BR-001 through BR-012 (all 12 rules originate in reachable paragraphs)
- **DEAD CODE PARAGRAPHS:** END-IF, END-EXEC, END-EVALUATE (CFG tool artifacts; no business logic)
- **NODES:** 9 CFG nodes (per smojol_node_count); 6 reachable procedure paragraphs; 2 data groups; 8 copybooks; 2 XCTL targets
