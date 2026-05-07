---
# ── Identity ──────────────────────────────────────────────────────────────────
schema_version: "cobol-md/1.0"
program_id: "COMEN01C"
source_file: "app/cbl/COMEN01C.cbl"
source_sha: "a404313748b0715a306336ac599b3e585697c05c"
translation_date: "2026-04-23"
translating_agent: "claude-opus-4-5 (subagent)"
aifirst_task_id: "T-2026-04-23-001"
cfg_source: "validation/structure/COMEN01C_cfg.json"

# ── Classification ─────────────────────────────────────────────────────────────
business_domain: "Administration"
subtype: "Menu"

# ── Structural Metadata ────────────────────────────────────────────────────────
author: "AWS"
date_written: null
lines_of_code: 213
divisions:
  identification: true
  environment: true
  data: true
  procedure: true
environment:
  compiler: "IBM Enterprise COBOL"
  target: "CICS/VSAM"
  runtime: "z/OS"

# ── Graph Edges ────────────────────────────────────────────────────────────────
calls_to:
  - program: "COSGN00C"
    condition: "EIBCALEN = 0 (no commarea on first entry)"
    call_type: "EXEC CICS XCTL"
  - program: "COSGN00C"
    condition: "PF3 pressed by user"
    call_type: "EXEC CICS XCTL"
  - program: "CDEMO-MENU-OPT-PGMNAME(WS-OPTION)"
    condition: "Valid option selected and program is COPAUS0C, EXEC CICS INQUIRE returns NORMAL"
    call_type: "EXEC CICS XCTL"
  - program: "CDEMO-MENU-OPT-PGMNAME(WS-OPTION)"
    condition: "Valid option selected and program name does not begin with DUMMY and is not COPAUS0C"
    call_type: "EXEC CICS XCTL"

called_by:
  - "COSGN00C"
  - "COACTUPC"
  - "COACTVWC"
  - "COBIL00C"
  - "COCRDLIC"
  - "COCRDSLC"
  - "COCRDUPC"
  - "CORPT00C"
  - "COTRN00C"
  - "COTRN01C"
  - "COTRN02C"

copybooks_used:
  - name: "COCOM01Y"
    path: "app/cpy/COCOM01Y.cpy"
    sha: null
  - name: "COMEN02Y"
    path: "app/cpy/COMEN02Y.cpy"
    sha: null
  - name: "COMEN01"
    path: "app/cpy-bms/COMEN01.CPY"
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
    path: null
    sha: null
  - name: "DFHBMSCA"
    path: null
    sha: null

bms_maps:
  - map: "COMEN01"
    copybook: "app/cpy-bms/COMEN01.CPY"
    translation_status: pending-extraction

# ── File I/O ───────────────────────────────────────────────────────────────────
file_control: []

# ── CICS ───────────────────────────────────────────────────────────────────────
cics_commands:
  - "RETURN"
  - "INQUIRE"
  - "XCTL"
  - "SEND"
  - "RECEIVE"

transaction_ids:
  - "CM00"

# ── Data Layer ─────────────────────────────────────────────────────────────────
data_items:
  - name: "WS-VARIABLES"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Top-level working-storage group holding all program-local scalar variables"

  - name: "WS-PGMNAME"
    level: 5
    picture: "X(08)"
    usage: null
    value: "COMEN01C"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Eight-character literal holding the name of this program, used when setting CDEMO-FROM-PROGRAM in the commarea before each XCTL dispatch"

  - name: "WS-TRANID"
    level: 5
    picture: "X(04)"
    usage: null
    value: "CM00"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Four-character CICS transaction identifier for this menu program; passed to CDEMO-FROM-TRANID and used on EXEC CICS RETURN to re-invoke the program"

  - name: "WS-MESSAGE"
    level: 5
    picture: "X(80)"
    usage: null
    value: "SPACES"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Eighty-character buffer holding the user-facing error or status message displayed in the ERRMSGO field of the BMS map"

  - name: "WS-USRSEC-FILE"
    level: 5
    picture: "X(08)"
    usage: null
    value: "USRSEC  "
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Eight-character ddname literal for the user-security VSAM file; defined in working storage but not referenced by any reachable logic in this program"

  - name: "WS-ERR-FLG"
    level: 5
    picture: "X(01)"
    usage: null
    value: "N"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Single-character error flag; condition names ERR-FLG-ON (value Y) and ERR-FLG-OFF (value N) are used to gate further processing and short-circuit XCTL dispatch"

  - name: "ERR-FLG-ON"
    level: 88
    picture: null
    usage: null
    value: "Y"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Condition-name that evaluates true when WS-ERR-FLG equals Y, indicating an input validation error has been detected"

  - name: "ERR-FLG-OFF"
    level: 88
    picture: null
    usage: null
    value: "N"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Condition-name that evaluates true when WS-ERR-FLG equals N, indicating no error is currently active"

  - name: "WS-RESP-CD"
    level: 5
    picture: "S9(09)"
    usage: "COMP"
    value: "0"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Binary signed fullword receiving the CICS RESP response code from EXEC CICS RECEIVE, used to detect map-receive failures"

  - name: "WS-REAS-CD"
    level: 5
    picture: "S9(09)"
    usage: "COMP"
    value: "0"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Binary signed fullword receiving the CICS RESP2 reason code from EXEC CICS RECEIVE, providing extended diagnostic detail alongside WS-RESP-CD"

  - name: "WS-OPTION-X"
    level: 5
    picture: "X(02)"
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-character right-justified work field that holds the raw alphanumeric option string received from the BMS map before conversion to numeric WS-OPTION"

  - name: "WS-OPTION"
    level: 5
    picture: "9(02)"
    usage: null
    value: "0"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Two-digit numeric field holding the validated menu option number entered by the user, used as the subscript into the CDEMO-MENU-OPT table"

  - name: "WS-IDX"
    level: 5
    picture: "S9(04)"
    usage: "COMP"
    value: "0"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Binary signed halfword loop index used both in the trailing-space trim of the raw option input and in the PERFORM VARYING loop that builds menu-option display lines"

  - name: "WS-MENU-OPT-TXT"
    level: 5
    picture: "X(40)"
    usage: null
    value: "SPACES"
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Forty-character work buffer built by concatenating the option number, a period-space separator, and the option name; moved to the appropriate map output field for each of the twelve possible menu slots"

  - name: "DFHCOMMAREA"
    level: 1
    picture: null
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Linkage-section entry mapped by CICS to the commarea passed by the invoking transaction; its single repeating-occurrence subordinate field is used to copy the inbound commarea into CARDDEMO-COMMAREA"

  - name: "LK-COMMAREA"
    level: 5
    picture: "X(01)"
    usage: null
    value: null
    redefines: null
    redefines_interpretations: []
    dead_code_flag: false
    semantic: "Variable-length character array within DFHCOMMAREA, dimensioned from 1 to 32767 bytes depending on EIBCALEN, providing the byte-by-byte copy source for populating CARDDEMO-COMMAREA"

# ── Procedure Paragraphs ───────────────────────────────────────────────────────
procedure_paragraphs:
  - name: "MAIN-PARA"
    reachable: true
    performs:
      - "RETURN-TO-SIGNON-SCREEN"
      - "SEND-MENU-SCREEN"
      - "RECEIVE-MENU-SCREEN"
      - "PROCESS-ENTER-KEY"
    goto_targets: []
    summary: "Entry point for transaction CM00; initializes the error flag, routes first-entry requests to the sign-on screen, controls the pseudo-conversational receive/send cycle, and dispatches ENTER or PF3 keystrokes before issuing EXEC CICS RETURN to suspend the task"

  - name: "END-EXEC"
    reachable: false
    performs: []
    goto_targets: []
    summary: "Unreachable artifact paragraph generated by the CFG tool from an EXEC CICS END-EXEC delimiter; contains no executable logic and is excluded from business-rule queries"

  - name: "PROCESS-ENTER-KEY"
    reachable: true
    performs:
      - "SEND-MENU-SCREEN"
    goto_targets: []
    summary: "Validates the numeric option entered on the menu map, enforces admin-only access restrictions, and issues an EXEC CICS XCTL to the program associated with the chosen option, with special handling for the COPAUS0C availability check and DUMMY placeholder options"

  - name: "END-IF"
    reachable: false
    performs: []
    goto_targets: []
    summary: "Unreachable artifact paragraph generated by the CFG tool from an IF/END-IF delimiter; contains no executable logic and is excluded from business-rule queries"

  - name: "RETURN-TO-SIGNON-SCREEN"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Defaults CDEMO-TO-PROGRAM to COSGN00C when the target is not already set, then issues an unconditional EXEC CICS XCTL to transfer control to the sign-on screen"

  - name: "SEND-MENU-SCREEN"
    reachable: true
    performs:
      - "POPULATE-HEADER-INFO"
      - "BUILD-MENU-OPTIONS"
    goto_targets: []
    summary: "Prepares the BMS map COMEN1AO by populating the header and menu-option lines, moves the current message into the error-message field, and sends the COMEN1A map from mapset COMEN01 with ERASE"

  - name: "RECEIVE-MENU-SCREEN"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Issues EXEC CICS RECEIVE for the COMEN1A map into COMEN1AI, capturing the user's keyboard input and storing CICS response codes in WS-RESP-CD and WS-REAS-CD"

  - name: "POPULATE-HEADER-INFO"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Reads the current date and time using FUNCTION CURRENT-DATE, formats them as MM/DD/YY and HH:MM:SS strings, and moves the application title lines, transaction ID, program name, date, and time into the output map header fields"

  - name: "BUILD-MENU-OPTIONS"
    reachable: true
    performs: []
    goto_targets: []
    summary: "Iterates over the CDEMO-MENU-OPT table (up to twelve entries) and assembles each option's display text as a concatenation of option number, separator, and option name, placing the result in the corresponding OPTN001O through OPTN012O map output field"

  - name: "END-PERFORM"
    reachable: false
    performs: []
    goto_targets: []
    summary: "Unreachable artifact paragraph generated by the CFG tool from a PERFORM/END-PERFORM delimiter; contains no executable logic and is excluded from business-rule queries"

# ── Business Rules ─────────────────────────────────────────────────────────────
business_rules:
  - id: "BR-001"
    rule: "If the commarea length (EIBCALEN) is zero on entry, the program immediately transfers control to the sign-on program COSGN00C without displaying the menu, preventing direct transaction invocation without an established session"
    source_paragraph: "MAIN-PARA"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-002"
    rule: "On first entry to the menu (CDEMO-PGM-REENTER flag not set), the program initialises the output map with low-values and displays the menu screen without reading user input, ensuring a clean initial presentation"
    source_paragraph: "MAIN-PARA"
    rule_type: "display"
    confidence: "high"
    reachable: true

  - id: "BR-003"
    rule: "If an attention identifier other than ENTER or PF3 is pressed, the error flag is set and the invalid-key message from CCDA-MSG-INVALID-KEY is displayed; no navigation occurs"
    source_paragraph: "MAIN-PARA"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-004"
    rule: "If the value entered in the option field is non-numeric, equals zero, or exceeds CDEMO-MENU-OPT-COUNT, the program displays 'Please enter a valid option number...' and re-presents the menu without dispatching"
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-005"
    rule: "If the signed-in user type is regular user (CDEMO-USRTYP-USER) and the selected option is flagged as admin-only (option user-type indicator equals 'A'), access is denied with the message 'No access - Admin Only option...' and the menu is re-displayed"
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-006"
    rule: "When the selected program is COPAUS0C, an EXEC CICS INQUIRE is performed first; if COPAUS0C is not installed (EIBRESP is not NORMAL), a red error message is displayed stating the option is not installed instead of dispatching"
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-007"
    rule: "If the program name associated with the selected option begins with 'DUMMY', a green informational message is displayed indicating the feature is coming soon, and no XCTL dispatch is performed"
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "display"
    confidence: "high"
    reachable: true

  - id: "BR-008"
    rule: "For any valid, installed, non-dummy option, the program name is looked up from the CDEMO-MENU-OPT-PGMNAME array using the option number as a subscript, and control is transferred to that program via EXEC CICS XCTL with the shared commarea"
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "lookup"
    confidence: "high"
    reachable: true

  - id: "BR-009"
    rule: "When PF3 is pressed, control is unconditionally transferred to COSGN00C (the sign-on screen), terminating the current menu session"
    source_paragraph: "MAIN-PARA"
    rule_type: "guard"
    confidence: "high"
    reachable: true

  - id: "BR-010"
    rule: "Before every EXEC CICS XCTL dispatch to a sub-program, the commarea fields CDEMO-FROM-TRANID, CDEMO-FROM-PROGRAM, and CDEMO-PGM-CONTEXT are set to identify the calling transaction and program, enabling the target to return correctly"
    source_paragraph: "PROCESS-ENTER-KEY"
    rule_type: "transform"
    confidence: "high"
    reachable: true

# ── Validation ─────────────────────────────────────────────────────────────────
validation:
  t01_schema_valid: null
  t02_structural_complete: null
  t02r_redefines_complete: null
  t03_functional_score: null
  t04_semantic_score: null
  t05_regression_pass: null
  overall: "PENDING"

---

# COMEN01C — CardDemo Main Menu for Regular Users

## Purpose

COMEN01C is the primary navigation hub for regular (non-administrative) users of the CardDemo CICS application. Running under transaction identifier CM00, it presents a numbered menu of up to eleven functional options—spanning account viewing, credit-card management, transaction enquiry, bill payment, and reporting—and dispatches the user to the appropriate sub-program via a pseudo-conversational EXEC CICS XCTL handoff. The program enforces two access-control rules: it blocks direct invocation without an active session commarea, and it prevents regular users from selecting options marked as admin-only.

## Runtime Context

COMEN01C executes entirely within CICS as an online pseudo-conversational program. There is no batch, file-channel, or DB2 component. The program uses five CICS commands: SEND and RECEIVE to exchange the COMEN1A BMS map with the terminal, XCTL to transfer control to destination programs or the sign-on screen, INQUIRE to verify that the optional COPAUS0C program is installed before dispatching to it, and RETURN with a commarea and transaction identifier to suspend the task and await the next terminal input.

The BMS mapset is COMEN01 (copybook COMEN01 from the BMS copybook directory), providing two symbolic maps: COMEN1AI for input and COMEN1AO for output. The shared application commarea is defined by copybook COCOM01Y as CARDDEMO-COMMAREA and is passed on every EXEC CICS RETURN and XCTL call. No VSAM file I/O is performed by this program; the user-security file name WS-USRSEC-FILE is declared in working storage but is never opened or read within the reachable logic.

The program runs in the z/OS IBM Enterprise COBOL environment and is invoked either directly from the COSGN00C sign-on program or on return from any of the eleven sub-programs listed in the menu-option table.

## Data Layout

### Working Storage Scalars

The local working-storage group WS-VARIABLES holds all scalar fields the program manipulates at runtime. The program name (eight characters, initialised to "COMEN01C") and transaction identifier (four characters, initialised to "CM00") are constants that are copied into the shared commarea before each XCTL. A general-purpose eighty-character message buffer is moved to the BMS error-message field before each screen send. A single-character error-flag field, with two condition names for the on and off states, is tested before attempting any dispatch. A two-character alphanumeric field holds the raw option input after right-justification trimming; it is inspected to replace spaces with zeros and then moved to a two-digit numeric field that acts as the array subscript. Two binary fullword fields receive CICS response and reason codes from the map-receive command. A binary halfword index field serves as both the option-trimming loop counter and the menu-build iteration counter. A forty-character work buffer is assembled in the menu-build loop and moved to the appropriate map output slot.

### Commarea and Linkage

The linkage section exposes DFHCOMMAREA as a variable-length single-field structure dimensioned by EIBCALEN. On entry, the program copies this into the CARDDEMO-COMMAREA structure defined by COCOM01Y. That structure carries general navigation fields (from/to transaction ID and program name, user ID, user type with admin and regular-user condition names, and a program-context flag distinguishing first entry from re-entry), plus customer, account, card, and miscellaneous navigation fields used by other programs in the suite.

### Menu-Option Table

The most significant data structure for this program is CARDDEMO-MAIN-MENU-OPTIONS, defined by copybook COMEN02Y. A two-digit count field holds the number of active options (currently eleven). The underlying data is laid out as a flat initialised area containing eleven sequential records, each comprising a two-digit option number, a thirty-five-character option name, an eight-character program name, and a one-character user-type indicator ('U' for all eleven options in the current configuration). A REDEFINES overlay maps this flat area as an array of twelve occurrences, each with four named sub-fields: option number, option name, program name, and user-type indicator. This overlay is the mechanism by which the program accesses options by subscript during both validation and dispatch. The array bound of twelve exceeds the active count of eleven, providing a spare slot with no initialised data.

The eleven active menu options and their associated target programs are:

1. Account View → COACTVWC  
2. Account Update → COACTUPC  
3. Credit Card List → COCRDLIC  
4. Credit Card View → COCRDSLC  
5. Credit Card Update → COCRDUPC  
6. Transaction List → COTRN00C  
7. Transaction View → COTRN01C  
8. Transaction Add → COTRN02C  
9. Transaction Reports → CORPT00C  
10. Bill Payment → COBIL00C  
11. Pending Authorization View → COPAUS0C  

All eleven options carry a user-type indicator of 'U', meaning no admin-gating is currently active in the table, though the program logic is fully capable of enforcing it.

### Supporting Copybook Structures

COTTL01Y defines a three-field screen-title group with the application title lines and a thank-you message. CSDAT01Y defines a date/time group with sub-fields for year, month, day, hours, minutes, seconds, and milliseconds, plus REDEFINES overlays that expose the date and time components as eight-digit numeric scalars, and formatted display strings for MM/DD/YY and HH:MM:SS presentation. CSMSG01Y defines two fifty-character common message literals, including the invalid-key message used in this program. CSUSR01Y defines a user-data record with ID, first name, last name, password, type, and filler fields; it is present in working storage but not accessed by reachable logic here. DFHAID and DFHBMSCA are IBM-supplied copybooks providing attention identifier constants and BMS symbolic colour attribute values respectively.

## Procedure Logic

### MAIN-PARA

MAIN-PARA is the sole entry point for transaction CM00. It first resets the error flag to off and clears both the message buffer and the map error-message field. If EIBCALEN is zero, indicating no commarea was passed, it records COSGN00C as the calling program and performs RETURN-TO-SIGNON-SCREEN immediately. Otherwise it copies the inbound commarea bytes into CARDDEMO-COMMAREA. If the program-context flag indicates this is a first entry (not a re-entry), it sets the re-entry flag, clears the output map to low-values, and performs SEND-MENU-SCREEN. On a re-entry it performs RECEIVE-MENU-SCREEN to capture the user's input and then evaluates the attention identifier: ENTER routes to PROCESS-ENTER-KEY; PF3 sets the target program to COSGN00C and routes to RETURN-TO-SIGNON-SCREEN; any other key sets the error flag, loads the invalid-key message, and performs SEND-MENU-SCREEN. Regardless of path, execution falls through to an EXEC CICS RETURN specifying transaction CM00 and the shared commarea, suspending the task until the next terminal event.

### END-EXEC

END-EXEC is an unreachable artifact paragraph identified by the Phase 0 CFG tool; it has no executable content and is never invoked by any reachable paragraph.

### PROCESS-ENTER-KEY

PROCESS-ENTER-KEY first trims trailing spaces from the raw option field by iterating backward from the field's maximum length until a non-space character or position one is found, then moves the trimmed characters to the right-justified work field, replaces any remaining embedded spaces with zeros, and converts to the numeric option variable. The numeric option value is also echoed back to the map output option field. Two sequential guards then check the input: if the value is non-numeric, zero, or greater than the active option count, an error message is set and SEND-MENU-SCREEN is performed. If the user is a regular user and the selected option carries an admin-only type indicator, an access-denied message is set and SEND-MENU-SCREEN is performed. If no error flag is set after these guards, an EVALUATE on the selected program name handles three cases. When the target is COPAUS0C, an EXEC CICS INQUIRE verifies the program is installed before issuing EXEC CICS XCTL; if not installed, a red error message is composed and SEND-MENU-SCREEN is called. When the program name begins with "DUMMY", a green coming-soon message is composed and SEND-MENU-SCREEN is called. For all other valid programs, the commarea navigation fields are set and EXEC CICS XCTL transfers control to the target program. After the EVALUATE, SEND-MENU-SCREEN is performed as a fallback in case none of the XCTL paths was taken.

### END-IF

END-IF is an unreachable artifact paragraph identified by the Phase 0 CFG tool; it has no executable content and is never invoked by any reachable paragraph.

### RETURN-TO-SIGNON-SCREEN

RETURN-TO-SIGNON-SCREEN ensures that CDEMO-TO-PROGRAM is set to COSGN00C if it currently holds low-values or spaces, providing a safe default target. It then issues an unconditional EXEC CICS XCTL to whatever program is named in CDEMO-TO-PROGRAM, transferring control without a commarea.

### SEND-MENU-SCREEN

SEND-MENU-SCREEN orchestrates the screen-output sequence: it calls POPULATE-HEADER-INFO to update the map header fields, calls BUILD-MENU-OPTIONS to fill the option-line fields, moves the current message buffer content to the map error-message field, and issues EXEC CICS SEND for map COMEN1A in mapset COMEN01 with the ERASE option to clear the terminal before painting.

### RECEIVE-MENU-SCREEN

RECEIVE-MENU-SCREEN issues EXEC CICS RECEIVE for map COMEN1A into the COMEN1AI symbolic input structure, storing the CICS response and reason codes in WS-RESP-CD and WS-REAS-CD for potential error diagnosis, though the current program logic does not explicitly branch on these codes after the receive.

### POPULATE-HEADER-INFO

POPULATE-HEADER-INFO obtains the current timestamp by moving FUNCTION CURRENT-DATE into the date/time working-storage group. It then moves the two application title strings to the map title fields, the transaction identifier to the map transaction-name field, the program name to the map program-name field, and formats the current date as MM/DD/YY and the current time as HH:MM:SS, moving each to the corresponding map display field.

### BUILD-MENU-OPTIONS

BUILD-MENU-OPTIONS loops from subscript one to CDEMO-MENU-OPT-COUNT, building a forty-character display string for each option by concatenating the numeric option number, the literal string ". ", and the option name. An EVALUATE on the current subscript routes the assembled string to the appropriate numbered output field on the map (OPTN001O through OPTN012O). Loop iterations beyond twelve fall through a WHEN OTHER CONTINUE clause harmlessly.

### END-PERFORM

END-PERFORM is an unreachable artifact paragraph identified by the Phase 0 CFG tool; it has no executable content and is never invoked by any reachable paragraph.

## Business Rules Surfaced

**BR-001** — Session guard on entry: if no commarea is present (EIBCALEN = 0), execution is redirected to the sign-on screen immediately, preventing unauthenticated access to the menu.

**BR-002** — First-entry initialisation: when CDEMO-PGM-REENTER indicates this is the first time the transaction has been entered, the program presents a clean menu screen without consuming any user input.

**BR-003** — Invalid attention key handling: pressing any key other than ENTER or PF3 causes the program to display the standard invalid-key message and re-present the menu, with no navigation taking place.

**BR-004** — Option range validation: the entered option must be numeric, non-zero, and within the bounds of the active option count; any value outside these constraints causes an error message and re-display of the menu.

**BR-005** — Admin-only option gating: if the signed-in user is a regular user and the chosen option's user-type indicator is 'A', access is denied with an explanatory message and the menu is re-presented.

**BR-006** — Availability check for COPAUS0C: before transferring to the pending-authorisation view program, the program verifies that COPAUS0C is installed in the CICS region; if the INQUIRE returns an abnormal response, a red error message is displayed instead.

**BR-007** — Placeholder option handling: if the looked-up program name begins with "DUMMY", the option is treated as a not-yet-implemented feature and a green informational message is shown without any XCTL dispatch.

**BR-008** — Table-driven program dispatch: for all other valid options, the target program name is read directly from the menu-option table using the user-supplied option number as an index, and control is transferred via EXEC CICS XCTL; no hard-coded program-name list exists in the procedure logic itself.

**BR-009** — PF3 return to sign-on: pressing PF3 from the menu unconditionally routes the user back to the sign-on screen, terminating the current navigation context.

**BR-010** — Commarea navigation fields stamped before dispatch: CDEMO-FROM-TRANID, CDEMO-FROM-PROGRAM, and CDEMO-PGM-CONTEXT are populated before every XCTL, so the target program knows where to return the user after it completes.

## Graph Summary

- **CALLS (EXEC CICS XCTL):** COMEN01C → COSGN00C (guard: no commarea on entry); COMEN01C → COSGN00C (guard: PF3 pressed); COMEN01C → COPAUS0C (guard: valid option + INQUIRE NORMAL); COMEN01C → CDEMO-MENU-OPT-PGMNAME\[n\] (guard: valid option, not COPAUS0C, not DUMMY)
- **CALLED BY:** COSGN00C, COACTUPC, COACTVWC, COBIL00C, COCRDLIC, COCRDSLC, COCRDUPC, CORPT00C, COTRN00C, COTRN01C, COTRN02C
- **COPYBOOKS:** COCOM01Y (commarea structure), COMEN02Y (menu-option table with REDEFINES), COMEN01 (BMS mapset), COTTL01Y (screen titles), CSDAT01Y (date/time fields), CSMSG01Y (common messages), CSUSR01Y (user record), DFHAID (attention IDs), DFHBMSCA (BMS colour attributes)
- **CICS COMMANDS:** RETURN (transaction CM00, commarea), SEND (map COMEN1A, ERASE), RECEIVE (map COMEN1A), XCTL (COSGN00C or table-looked-up program), INQUIRE (COPAUS0C availability)
- **TRANSACTION IDs:** CM00 (own transaction, used on RETURN and stamped in FROM-TRANID)
- **VSAM FILE I/O:** None (no file-control entries, no OPEN/READ/WRITE/CLOSE commands)
- **BUSINESS RULES:** BR-001 guard (no-commarea redirect), BR-002 display (first-entry init), BR-003 guard (invalid AID), BR-004 guard (option range), BR-005 guard (admin-only access), BR-006 guard (COPAUS0C availability), BR-007 display (DUMMY placeholder), BR-008 lookup (table-driven dispatch), BR-009 guard (PF3 sign-on return), BR-010 transform (commarea stamp before XCTL)
- **DEAD CODE:** Paragraphs END-EXEC, END-IF, and END-PERFORM are unreachable per Phase 0 static analysis and carry no business logic
