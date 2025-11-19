# Program Analysis: COACTVWC

## Overview
**Source File**: `app/cbl/COACTVWC.cbl`
**Type**: Online Transaction Program (CICS)
**Module**: Account Management
**Transaction ID**: CAVW
**Lines of Code**: 942

## Business Purpose
COACTVWC provides account viewing functionality. Users enter an account number, and the program retrieves and displays comprehensive account details including account balance, credit limits, customer information, and associated card details. This is a read-only inquiry program.

## Key Logic

### Main Processing Flow
1. **Initial Entry**: Display empty inquiry screen prompting for account number
2. **User Input**: Receive account ID from user
3. **Validation**: Verify account ID is numeric, non-zero, 11 digits
4. **Data Retrieval Chain** (3 file reads):
   - Read CARDXREF file (by account ID via alternate index) → get customer ID and card number
   - Read ACCTDAT file (account master) → get account details
   - Read CUSTDAT file (customer master) → get customer name and info
5. **Display**: Show complete account details on screen
6. **Re-entry**: Allow user to enter different account ID or press F3 to exit

### File Read Sequence
The program reads three files in order, each dependent on the previous:
1. **CARDXREF** (via alternate index on account ID)
   - Purpose: Link account to customer and card
   - Returns: Customer ID, Card Number
2. **ACCTDAT** (account master file)
   - Key: Account ID
   - Returns: Balance, credit limits, status, dates
3. **CUSTDAT** (customer master file)
   - Key: Customer ID (from CARDXREF)
   - Returns: Customer name, address, contact info

### Validation Rules
- Account ID must not be blank
- Account ID must be numeric
- Account ID must be non-zero
- Account ID must be 11 digits
- Account must exist in CARDXREF file
- Account must exist in ACCTDAT file
- Associated customer must exist in CUSTDAT file

### Function Key Handling
- **ENTER**: Submit account ID for inquiry
- **F3**: Return to previous program (typically menu)
- **Other keys**: Invalid key message

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - COMMAREA (session context)
- `COACTVW` - BMS screen map (account view screen)
- `CVACT01Y` - Account record structure
- `CUSTREC` - Customer record structure
- Card cross-reference structure (embedded or separate copybook)
- `CSDAT01Y` - Date/time structures
- `COTTL01Y` - Title definitions

**Files Accessed**:
- `CARDXREF` - Card/Account/Customer cross-reference (READ via alternate index)
- `ACCTDAT` - Account master file (READ)
- `CUSTDAT` - Customer master file (READ)

**Screens** (BMS):
- `CACTVWA` (mapset COACTVW) - Account view display screen

## Program Relationships

**Called By (XCTL)**:
- `COMEN01C` - Main menu (option 1: Account View)
- Other programs needing account inquiry

**Calls**: None (inquiry only, no XCTL to other programs)

**Navigation**:
- Entry: XCTL from menu
- Exit: F3 returns to calling program (via COMMAREA FROM-PROGRAM)

## Notable Patterns

### Three-Tier Data Retrieval
Classic mainframe pattern for normalized data:
```
Account ID → CARDXREF → Customer ID, Card Number
          ↓
       ACCTDAT → Account Details
          ↓
Customer ID → CUSTDAT → Customer Details
```

### Alternate Index Usage
Uses alternate index on CARDXREF to look up by account ID (not primary key):
- Primary key likely: Card Number
- Alternate index: Account ID
- Allows efficient account-based inquiry

### Comprehensive Error Handling
Detailed error messages for each file read failure:
- File not found errors show which file and response codes
- User-friendly messages for business logic errors
- Technical messages for system errors

### Read-Only Transaction
Pure inquiry - no file updates:
- Fast execution
- No locking concerns
- Can be safely repeated
- No integrity constraints to manage

### Screen Initialization Pattern
Modular screen setup:
- 1100-SCREEN-INIT: Clear screen
- 1200-SETUP-SCREEN-VARS: Populate data fields
- 1300-SETUP-SCREEN-ATTRS: Set field attributes (colors, protection)
- 1400-SEND-SCREEN: Send to terminal

### Pseudo-Conversational
Standard CICS pattern:
- Display screen and RETURN
- Re-enter on next input
- COMMAREA preserves context
- Efficient terminal resource usage

## Screen Display Fields

Account information displayed (from ACCTDAT):
- Account ID
- Account status
- Current balance
- Credit limit
- Cash credit limit
- Open date, expiration date
- Current cycle credit/debit totals

Customer information displayed (from CUSTDAT):
- Customer ID
- Customer name (first, middle, last)
- Address
- Phone numbers

Card information displayed (from CARDXREF):
- Card number associated with account

## Error Messages

- "Account number not provided"
- "Account number must be a non zero 11 digit number"
- "Did not find this account in account card xref file"
- "Did not find this account in account master file"
- "Did not find associated customer in master file"
- "Error reading account card xref File"
- File error messages with RESP/RESP2 codes

## Migration Considerations

**Modern web equivalent**:
- RESTful API: `GET /api/accounts/{accountId}`
- Return JSON with account, customer, and card details
- Single database query with JOINs instead of 3 file reads
- Caching for frequently accessed accounts

**Database design**:
- Replace VSAM files with SQL tables
- Foreign key relationships (Customer → Account → Card)
- Views or stored procedures for combined data retrieval
- Indexing on account ID for fast lookup

**User experience**:
- Auto-complete on account ID entry
- Search by customer name or card number
- Tabbed interface for related information
- Export to PDF/Excel
- Print statement functionality
- Drill-down links to transactions, cards, etc.

**Performance optimization**:
- Single query with LEFT JOINs
- Lazy loading for related data
- GraphQL for flexible data retrieval
- Response caching (Redis)
