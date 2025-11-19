# Program Analysis: COTRN01C

## Overview
**Source File**: `app/cbl/COTRN01C.cbl`  
**Type**: Online/CICS  
**Module**: Transaction Management  
**Transaction ID**: CT01

## Business Purpose
Displays detailed information for a specific transaction. Users can enter a transaction ID to view all transaction details including card number, transaction codes, amounts, dates, and merchant information. This is an inquiry-only screen (no updates).

## Key Logic

### Transaction Lookup
- Accepts transaction ID as input (required field)
- Reads transaction record from TRANSACT file with UPDATE lock (though no updates are performed)
- Displays all transaction fields if found
- Shows error message if transaction ID not found or invalid

### Screen Management
- Single transaction view with comprehensive detail display
- PF4 clears all fields for new search
- Can receive transaction ID from COTRN00C (list screen) via COMMAREA
- Auto-populates and displays transaction if selected from list

### Data Display
Formats and displays:
- Transaction identification (ID, card number)
- Transaction classification (type code, category code, source)
- Transaction description (full text)
- Financial data (amount with formatting)
- Temporal data (original timestamp, processing timestamp)
- Merchant information (ID, name, city, zip)

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - Common COMMAREA (navigation context)
- `CVTRA05Y` - Transaction record layout (TRAN-RECORD)
- `COTRN01` - Screen map (transaction detail display)
- `CSMSG01Y` - Message definitions
- `CSDAT01Y` - Date/time structures
- `COTTL01Y` - Screen title definitions

**Files Accessed**:
- `TRANSACT` - Transaction file (read with UPDATE lock, inquiry only)

**Screens**:
- `COTRN1A` (from COTRN01.bms) - Transaction detail display

## Program Relationships

**Calls**: None (inquiry only)

**Called By**: 
- COTRN00C - Transaction list (user selects transaction with 'S')
- Direct invocation via transaction ID CT01

**Navigation**:
- F3: Return to calling program (COMEN01C if none specified)
- F4: Clear screen for new transaction search
- F5: Return to transaction browse list (COTRN00C)
- Enter: Fetch and display transaction

## Screen Layout
The transaction detail screen (COTRN1A) displays:

**Input Section**:
- Transaction ID field (16 chars, required)

**Display Section** (read-only):
- Transaction ID (echo)
- Card Number (16 chars)
- Type Code (2 chars)
- Category Code (4 chars)
- Source (10 chars)
- Description (60 chars, full text)
- Amount (12 chars, formatted with sign)
- Original Date (10 chars, timestamp)
- Processing Date (10 chars, timestamp)
- Merchant ID (9 chars)
- Merchant Name (30 chars)
- Merchant City (25 chars)
- Merchant Zip (10 chars)

**Footer**:
- Error message area
- Function keys: ENTER=Fetch  F3=Back  F4=Clear  F5=Browse Tran.

## Notable Patterns

### Context-Aware Entry
- Checks CDEMO-CT01-TRN-SELECTED in COMMAREA on first entry
- If populated (from COTRN00C selection), auto-displays that transaction
- Bypasses manual entry requirement when coming from list screen

### Smart Navigation
- F3 returns to CDEMO-FROM-PROGRAM if set, otherwise COMEN01C (main menu)
- F5 always returns to COTRN00C (browse list)
- Maintains program context through COMMAREA for proper back-navigation

### File Access Pattern
- Uses READ with UPDATE lock even though program is inquiry-only
- This may be legacy pattern or intentional to prevent concurrent updates
- Could be optimized to simple READ without UPDATE for true inquiry

### Field Initialization
- INITIALIZE-ALL-FIELDS routine clears all input and output fields
- Called by CLEAR-CURRENT-SCREEN (PF4)
- Moves spaces to all field variables
- Resets cursor to Transaction ID input field

### Error Handling
- Validates transaction ID is not empty
- Handles NOTFND response with user-friendly message
- Sets cursor to error field (transaction ID input)
- Displays error in red at screen bottom

### COMMAREA Reuse
- Defines CDEMO-CT01-INFO structure over COMMAREA
- Stores transaction context (selected ID, page info)
- Though less used than in COTRN00C, maintains same structure pattern
- Supports proper integration with list screen (COTRN00C)

### Display-Only Fields
All transaction data fields are display-only (ASKIP attribute), reinforcing inquiry-only nature. No validation or update logic exists.
