# Program Analysis: COTRN02C

## Overview
**Source File**: `app/cbl/COTRN02C.cbl`  
**Type**: Online/CICS  
**Module**: Transaction Management  
**Transaction ID**: CT02

## Business Purpose
Allows users to add new transactions to the TRANSACT file. Validates all input fields, cross-references account and card numbers, generates new transaction IDs sequentially, and writes the transaction record. Includes convenience feature to copy data from last transaction to speed data entry.

## Key Logic

### Transaction ID Generation
- Reads last (highest) transaction ID from TRANSACT file using READPREV from HIGH-VALUES
- Increments by 1 to generate new unique ID
- Sequential key assignment ensures no duplicates

### Account/Card Cross-Reference
- User must enter either Account ID or Card Number (not both, one required)
- If Account ID provided: looks up card number in CXACAIX file (account-to-card index)
- If Card Number provided: looks up account ID in CCXREF file (card-to-account xref)
- Auto-populates the reciprocal field after successful lookup
- Validates that account/card exists before allowing transaction add

### Comprehensive Validation
**Key Fields** (all required):
- Account ID or Card Number (one required, numeric)
- Type Code (2 digits, numeric)
- Category Code (4 digits, numeric)
- Source (10 chars, alphanumeric)
- Description (60 chars, free text)
- Amount (format: -99999999.99, with sign)
- Original Date (format: YYYY-MM-DD, validated via CSUTLDTC)
- Processing Date (format: YYYY-MM-DD, validated via CSUTLDTC)
- Merchant ID (9 digits, numeric)
- Merchant Name (30 chars, free text)
- Merchant City (25 chars, free text)
- Merchant Zip (10 chars, alphanumeric)

**Date Validation**:
- Calls CSUTLDTC utility to validate date format and validity
- Ensures dates are real calendar dates

**Amount Validation**:
- Must include sign (+ or -)
- Decimal point in correct position
- Two decimal places
- Uses NUMVAL-C function to convert to numeric

### Confirmation Workflow
- After validation, user must explicitly confirm with 'Y' or 'y'
- Prevents accidental transaction creation
- Shows error if confirmation missing or invalid

### Copy Last Transaction (PF5)
- Retrieves most recent transaction for the entered account/card
- Copies all transaction data fields except IDs
- Allows quick re-entry of similar transactions
- User can modify copied data before confirmation

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - Common COMMAREA
- `CVTRA05Y` - Transaction record (TRAN-RECORD)
- `CVACT01Y` - Account record (for validation)
- `CVACT03Y` - Card cross-reference record (CARD-XREF-RECORD)
- `COTRN02` - Screen map
- `CSMSG01Y` - Message definitions
- `CSDAT01Y` - Date/time structures
- `COTTL01Y` - Title definitions

**Files Accessed**:
- `TRANSACT` - Transaction file (read for ID generation, write for add)
- `CCXREF` - Card cross-reference file (read to validate card→account)
- `CXACAIX` - Account cross-reference AIX (read to validate account→card)

**Programs Called**:
- `CSUTLDTC` - Date validation utility (via CALL)

**Screens**:
- `COTRN2A` (from COTRN02.bms) - Transaction add form

## Program Relationships

**Calls**: 
- CSUTLDTC - Date validation (CALL for origin and processing dates)

**Called By**: 
- COMEN01C - Main menu (via menu option)
- Direct invocation via transaction ID CT02

**Navigation**:
- F3: Return to previous screen/main menu
- F4: Clear all fields for new entry
- F5: Copy last transaction data for selected account/card
- Enter: Validate and add transaction (with confirmation)

## Notable Patterns

### Dual Key Entry
- Flexible entry: user can provide either account ID or card number
- System automatically cross-references to find the other
- Simplifies data entry - user doesn't need both pieces of information

### Sequential ID Assignment
- Uses HIGH-VALUES STARTBR + READPREV to get maximum ID efficiently
- Adds 1 to create next sequential ID
- Simple but effective for generating unique keys
- Note: In high-concurrency environments, this could have timing issues (no locking)

### Extensive Field Validation
- Every field validated for presence, format, and data type
- Specific error messages guide user to correction
- Cursor positioned at error field
- Validation cascades: stops at first error

### Date Validation via Utility
- Doesn't just check format, validates actual calendar dates
- Calls CSUTLDTC for thorough date checking
- Prevents invalid dates like 2023-02-30

### User Confirmation Pattern
- Requires explicit 'Y' confirmation before write
- Good practice for data modification operations
- Prevents accidental submissions

### Productivity Feature (PF5)
- Copy Last Tran data speeds repetitive entry
- Common in data entry applications
- Pre-fills form with similar transaction data
- User still must confirm

### Success Feedback
- After successful add, displays new Transaction ID in green
- Clear confirmation message
- Clears form for next entry

### Error Handling
- Validates file existence (NOTFND responses)
- Handles duplicate key scenarios (DUPKEY/DUPREC)
- Provides specific error messages for each condition
- Sets cursor to problematic field

### Field Initialization
- INITIALIZE-ALL-FIELDS clears all input fields
- Called after successful add and on F4 (clear)
- Prepares screen for next transaction entry
