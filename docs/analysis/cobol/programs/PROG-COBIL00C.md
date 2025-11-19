# Program Analysis: COBIL00C

## Overview
**Source File**: `app/cbl/COBIL00C.cbl`  
**Type**: Online (CICS)  
**Module**: Bill Payment

## Business Purpose
Allows customers to pay their full account balance online. Creates a payment transaction, updates the account balance to zero, and provides a confirmation with transaction ID. Integrates with the transaction and account systems to record the payment immediately.

## Key Logic

### Bill Payment Process
1. **Account Lookup**: 
   - User enters account ID
   - Program reads account record for UPDATE
   - Displays current balance to user
2. **Validation**:
   - Checks if balance > 0 (nothing to pay if zero or negative)
   - Validates account exists
3. **Payment Confirmation**:
   - User must confirm (Y) to proceed
   - Declining (N) clears the screen
4. **Payment Execution**:
   - Reads cross-reference file to get card number
   - Generates new transaction ID (highest existing + 1)
   - Creates bill payment transaction record
   - Updates account balance (current balance - payment amount)
   - Displays success message with transaction ID

### Transaction ID Generation
- Reads transaction file backwards (STARTBR with HIGH-VALUES)
- Uses READPREV to get highest transaction ID
- Increments by 1 for new payment transaction
- Handles ENDFILE (no transactions exist, starts at 1)

### Payment Transaction Details
- **Type**: '02' (Bill Payment)
- **Category**: 2 (Payment category)
- **Source**: 'POS TERM'
- **Description**: 'BILL PAYMENT - ONLINE'
- **Amount**: Full current account balance
- **Merchant ID**: 999999999 (system-generated payment)
- **Merchant Name**: 'BILL PAYMENT'
- **Location**: 'N/A' (online payment)
- **Timestamps**: Current date/time for both original and processed

### Balance Update
- Account balance reduced by payment amount (full balance)
- Account record updated immediately (REWRITE with UPDATE lock)
- New balance effectively zero after payment

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - Common communication area with CB00-INFO extension
- `COBIL00` - Screen map (COBIL0A input/output)
- `COTTL01Y` - Title definitions
- `CSDAT01Y` - Date/time structures
- `CSMSG01Y` - Message definitions
- `CVACT01Y` - Account record
- `CVACT03Y` - Card cross-reference record
- `CVTRA05Y` - Transaction record

**Files Accessed**:
- `ACCTDAT` - Account master file (read for update, rewrite)
- `CXACAIX` - Card cross-reference alternate index (read by account ID)
- `TRANSACT` - Transaction file (browse, write)

**CICS Resources**:
- Transaction: CB00
- Screen: COBIL0A

## Program Relationships
**Calls**: None  
**Called By**: Main menu or transaction list (via CDEMO-CB00-TRN-SELECTED)  
**Returns To**: Calling program (F3) or self (Enter/F4)

## Notable Patterns

### CICS File Operations
- **READ UPDATE**: Locks account record during payment
- **REWRITE**: Updates locked account record
- **STARTBR/READPREV/ENDBR**: Browse transaction file backward for ID generation
- **WRITE**: Adds new payment transaction

### Timestamp Generation
- EXEC CICS ASKTIME for absolute time
- EXEC CICS FORMATTIME for conversion to readable format
- Format: YYYY-MM-DD HH:MM:SS.000000 (26 characters)
- Milliseconds set to zeros

### Two-Phase Update
1. **Phase 1**: Create transaction record (write to TRANSACT file)
2. **Phase 2**: Update account balance (rewrite ACCTDAT record)
- If Phase 1 fails, no account update occurs
- If Phase 2 fails, transaction exists but balance not updated (manual reconciliation needed)

### Navigation Context
- Supports direct account selection from transaction list (CDEMO-CB00-TRN-SELECTED)
- Populates account ID automatically if called with selection
- Returns to originating program (CDEMO-FROM-PROGRAM) on F3

### User Confirmation
- Two-step process: display balance, then confirm
- Confirmation field accepts Y/y/N/n (case insensitive)
- Invalid confirmation prompts for valid input
- No confirmation (spaces/low-values) prompts user

### Error Handling
- Account not found: Error message with field highlight
- Zero balance: Warning message (nothing to pay)
- Invalid confirmation: Specific error message
- File operation errors: Technical error message with RESP/REAS codes
- Duplicate transaction ID: Unlikely but handled

## Business Rules
1. Can only pay full balance (not partial payment)
2. Account must have positive balance to pay
3. Payment creates type '02' transaction with category 2
4. Transaction ID generated as max existing ID + 1
5. Account balance becomes zero after successful payment
6. Payment timestamp recorded as current date/time
7. Merchant ID 999999999 reserved for system payments
8. Payment recorded against card number (via cross-reference lookup)
9. User must explicitly confirm payment
10. Success message displays generated transaction ID
11. F4 clears screen for new payment entry
12. Payment is immediate (no batch processing)
