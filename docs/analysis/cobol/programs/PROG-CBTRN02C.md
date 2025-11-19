# Program Analysis: CBTRN02C

## Overview
**Source File**: `app/cbl/CBTRN02C.cbl`  
**Type**: Batch  
**Module**: Transaction Batch Processing  

## Business Purpose
**Critical daily batch job** that posts transactions from the daily transaction file (DALYTRAN) to the permanent transaction file (TRANSACT). Validates each transaction, updates account balances, maintains transaction category balances, and writes rejected transactions to a rejects file with reason codes.

This is the core transaction posting process that moves pending transactions into the system of record.

## Key Logic

### Main Processing Loop
1. Read transaction from DALYTRAN (daily transactions sequential file)
2. Validate transaction (card number, account, credit limit, expiration)
3. If valid: Post transaction (write to TRANSACT, update balances)
4. If invalid: Write to DALYREJS with rejection reason
5. Repeat until end of DALYTRAN file
6. Display counts and set return code if rejections occurred

### Transaction Validation
**Card Number Validation** (1500-A-LOOKUP-XREF):
- Looks up card number in XREF-FILE
- Gets associated account ID
- Rejection code 100: "INVALID CARD NUMBER FOUND"

**Account Validation** (1500-B-LOOKUP-ACCT):
- Reads account record for account ID
- Validates three business rules:
  1. **Credit Limit Check**: Ensures transaction won't exceed account credit limit
     - Calculates: Current Balance + Transaction Amount
     - Compares to Credit Limit
     - Rejection code 102: "OVERLIMIT TRANSACTION"
  2. **Expiration Date Check**: Ensures transaction not after account expiration
     - Rejection code 103: "TRANSACTION RECEIVED AFTER ACCT EXPIRATION"
  3. **Account Exists Check**: Account record must be found
     - Rejection code 101: "ACCOUNT RECORD NOT FOUND"

### Transaction Posting (2000-POST-TRANSACTION)
When transaction passes validation:
1. Maps DALYTRAN fields to TRAN-RECORD fields
2. Generates processing timestamp (current date/time)
3. Updates transaction category balance (TCATBAL file)
4. Updates account balances
5. Writes transaction to permanent TRANSACT file

### Account Balance Updates (2800-UPDATE-ACCOUNT-REC)
- Updates `ACCT-CURR-BAL` (current balance) with transaction amount
- If transaction amount >= 0 (credit): adds to `ACCT-CURR-CYC-CREDIT`
- If transaction amount < 0 (debit): adds to `ACCT-CURR-CYC-DEBIT`
- Rewrites account record with updated balances

### Transaction Category Balance (2700-UPDATE-TCATBAL)
- Key: Account ID + Transaction Type Code + Category Code
- If category balance record exists: adds transaction amount to balance (REWRITE)
- If not exists: creates new record with transaction amount (WRITE)
- Maintains running totals by account/type/category for reporting

### Reject Handling (2500-WRITE-REJECT-REC)
- Writes entire transaction record to DALYREJS file
- Appends validation trailer with:
  - Rejection reason code (numeric)
  - Rejection reason description (text)
- Allows manual review and correction of rejected transactions

### Return Code Logic
- If any transactions rejected: sets RETURN-CODE to 4
- Allows JCL to detect rejections and trigger alerts/processing

## Data Dependencies

**Key Copybooks**:
- `CVTRA06Y` - Daily transaction record layout (DALYTRAN-RECORD)
- `CVTRA05Y` - Permanent transaction record (TRAN-RECORD)
- `CVACT01Y` - Account record (ACCOUNT-RECORD)
- `CVACT03Y` - Card cross-reference record (CARD-XREF-RECORD)
- `CVTRA01Y` - Transaction category balance (TRAN-CAT-BAL-RECORD)

**Files Accessed**:
- `DALYTRAN` - Daily transactions (sequential input)
- `TRANSACT` - Permanent transactions (indexed output)
- `XREF` - Card-to-account cross-reference (indexed input)
- `DALYREJS` - Rejected transactions (sequential output)
- `ACCTFILE` - Account master (indexed I-O for balance updates)
- `TCATBALF` - Transaction category balances (indexed I-O)

## Program Relationships

**Calls**: None

**Called By**: 
- JCL job POSTTRAN.jcl (or similar daily posting job)

**Dependencies**:
- DALYTRAN file must be populated by prior process (transaction capture/import)
- XREF, ACCTFILE must be current and accessible
- TCATBALF file can be empty (creates records as needed)

## Notable Patterns

### Timestamp Generation
- Uses FUNCTION CURRENT-DATE to get system timestamp
- Formats as DB2-compatible timestamp: YYYY-MM-DD-HH.MM.SS.HH0000
- Stored as TRAN-PROC-TS (processing timestamp)
- Original timestamp (TRAN-ORIG-TS) preserved from DALYTRAN

### Robust File Handling
- Validates file status on every open/close/read/write
- Displays detailed error messages
- Calls CEE3ABD to abend program on file errors
- Ensures data integrity by failing fast on errors

### Sequential Input, Random Updates
- Reads DALYTRAN sequentially (batch file)
- Random access to XREF, ACCTFILE, TCATBALF for lookups/updates
- Writes TRANSACT as indexed file for later random access
- Classic batch processing pattern

### Balance Maintenance
- Updates two balance files atomically:
  - Account balance (financial snapshot)
  - Category balance (reporting/analytics)
- Both must succeed for transaction to post

### Create-or-Update Pattern (TCATBALF)
- Tries to READ category balance record
- If found (status '00'): updates balance (REWRITE)
- If not found (status '23'): creates new record (WRITE)
- Handles both existing and new categories gracefully

### Rejection Logging
- Preserves full transaction data in reject file
- Appends structured reason code and description
- Enables downstream analysis and correction
- Counts rejections for reporting

### Return Code Signaling
- Return code 0: All transactions posted successfully
- Return code 4: One or more rejections occurred
- JCL can conditionally execute cleanup/alert steps

### Error Handling Strategy
- Validation errors → Write to reject file, continue processing
- File I/O errors → Display error, abend program
- Ensures one bad transaction doesn't stop entire batch
- But critical file errors stop processing to prevent data corruption
