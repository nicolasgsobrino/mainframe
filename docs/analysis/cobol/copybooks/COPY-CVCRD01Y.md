# Copybook Analysis: CVCRD01Y

## Overview
**Source File**: `app/cpy/CVCRD01Y.cpy`
**Type**: Working Storage / Control Fields
**Used By**: Card-related programs (COCRDLIC, COCRDSLC, COCRDUPC)

## Purpose
CVCRD01Y defines working storage areas for card-related programs, including attention identifier (AID) key handling, navigation control, message fields, and key business entity IDs. This is a control copybook rather than a file record layout.

## Structure Overview
The `CC-WORK-AREAS` structure contains:
1. **AID key detection** (function key and attention key handling)
2. **Navigation control** (next program and map)
3. **Message areas** (error and return messages)
4. **Business entity IDs** (account, card, customer with numeric redefines)

## Key Fields

### Attention Identifier (AID) Handling
- `CCARD-AID` - Contains the attention key pressed (5 chars)
- 88-level conditions for all keys:
  - `CCARD-AID-ENTER` - Enter key
  - `CCARD-AID-CLEAR` - Clear key
  - `CCARD-AID-PA1/PA2` - Program attention keys
  - `CCARD-AID-PFK01` through `CCARD-AID-PFK12` - Function keys F1-F12

### Navigation Control
- `CCARD-NEXT-PROG` - Next program to XCTL to (8 chars)
- `CCARD-NEXT-MAPSET` - Next BMS mapset name (7 chars)
- `CCARD-NEXT-MAP` - Next BMS map name (7 chars)

### User Feedback Messages
- `CCARD-ERROR-MSG` - Error message to display (75 chars)
- `CCARD-RETURN-MSG` - Success/info message (75 chars)
  - `CCARD-RETURN-MSG-OFF` - Condition to check if message is empty

### Business Entity Identifiers
- `CC-ACCT-ID` / `CC-ACCT-ID-N` - Account ID (alphanumeric and numeric views via REDEFINES)
- `CC-CARD-NUM` / `CC-CARD-NUM-N` - Card number (16 digits, alphanumeric and numeric)
- `CC-CUST-ID` / `CC-CUST-ID-N` - Customer ID (9 digits, alphanumeric and numeric)

## Notable Patterns

### REDEFINES for Dual-Format IDs
Each ID field has two views using REDEFINES:
- Alphanumeric version (PIC X) for display and file I/O
- Numeric version (PIC 9) for arithmetic operations and validation
- Both occupy the same storage, providing flexibility without duplication

### Comprehensive AID Handling
All possible 3270 attention keys defined with 88-level conditions enables readable code:
```cobol
IF CCARD-AID-PFK03
   PERFORM RETURN-TO-MENU
```
Instead of cryptic byte value comparisons.

### Commented-Out Fields
Several fields are commented out (lines starting with `*`):
- CCARD-LAST-PROG
- CCARD-RETURN-TO-PROG
- CCARD-RETURN-FLAG
- CCARD-FUNCTION

These may be deprecated or reserved for future use.

### Message Size
75-character messages fit within standard 3270 screen message area (usually 1 line at 80 columns with formatting).

## Usage Context

**Common pattern in card programs**:
1. Program receives control
2. Checks `CCARD-AID` to determine what user pressed
3. Validates and processes based on the action
4. Sets `CCARD-ERROR-MSG` or `CCARD-RETURN-MSG` for feedback
5. Sets `CCARD-NEXT-PROG/MAPSET/MAP` for navigation
6. XCTL to next program or redisplay current screen

**Relationship to COCOM01Y**:
- CVCRD01Y is module-specific working storage
- COCOM01Y is application-wide COMMAREA
- Both work together for complete navigation and state management

**Business entity tracking**:
- Programs populate CC-ACCT-ID, CC-CARD-NUM, CC-CUST-ID from files or COMMAREA
- Use numeric versions for calculations, comparisons
- Use alphanumeric versions for display and file keys
