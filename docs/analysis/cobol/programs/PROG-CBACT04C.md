# Program Analysis: CBACT04C

## Overview
**Source File**: `app/cbl/CBACT04C.cbl`  
**Type**: Batch  
**Module**: Account Batch Processing  

## Business Purpose
**Critical monthly batch job** that calculates and applies interest charges to credit card accounts. Reads transaction category balances, looks up interest rates based on account group and transaction category, computes monthly interest, generates interest transactions, and updates account balances. Also resets monthly cycle counters (credit/debit) to zero for next billing cycle.

## Key Logic

### Processing Strategy (Control Break Logic)
- Reads TCATBAL file sequentially (sorted by Account ID)
- Detects account number change (control break)
- On each new account:
  1. Updates previous account with total interest
  2. Resets cycle-to-date credit/debit to zero
  3. Starts accumulating interest for new account
- Processes all transaction categories for each account
- Computes interest per category based on balance and rate
- Accumulates total interest per account

### Interest Calculation Formula
```
Monthly Interest = (Category Balance × Interest Rate) / 1200
```
- Interest Rate is annual percentage (e.g., 18.0 for 18%)
- Divided by 1200 to get monthly rate (12 months × 100 for percentage)
- Applied to category balance
- Accumulated across all categories for account

### Interest Rate Lookup (1200-GET-INTEREST-RATE)
- Looks up rate in DISCGRP (Disclosure Group) file
- Key: Account Group ID + Transaction Type + Category Code
- If not found: tries DEFAULT group code
- Allows different rates for:
  - Different account types (standard, premium, etc.)
  - Different transaction types (purchase, cash advance)
  - Different categories (retail, dining, travel, etc.)

### Transaction Generation (1300-B-WRITE-TX)
- Creates interest transaction for each category with interest
- Transaction ID: Date + Sequence suffix (e.g., 2023-12-3100001)
- Type Code: '01' (likely debit/charge)
- Category Code: '05' (likely interest category)
- Source: 'System' (system-generated)
- Description: "Int. for a/c {account-id}"
- Amount: Calculated monthly interest
- Timestamps: Current timestamp for origin and processing
- Writes to TRANSACT file for integration with transaction history

### Account Balance Update (1050-UPDATE-ACCOUNT)
- Adds total interest to `ACCT-CURR-BAL` (current balance)
- **Resets monthly cycle counters to zero**:
  - `ACCT-CURR-CYC-CREDIT` = 0
  - `ACCT-CURR-CYC-DEBIT` = 0
- This reset indicates end-of-cycle processing (monthly close)
- Rewrites account record with updated values

### End-of-File Handling
- On EOF, processes last account (control break completion)
- Ensures no account's interest is missed

## Data Dependencies

**Key Copybooks**:
- `CVTRA01Y` - Transaction category balance (TRAN-CAT-BAL-RECORD)
- `CVACT01Y` - Account record (ACCOUNT-RECORD)
- `CVACT03Y` - Card cross-reference (CARD-XREF-RECORD)
- `CVTRA02Y` - Disclosure group record (DIS-GROUP-RECORD)
- `CVTRA05Y` - Transaction record (TRAN-RECORD)

**Files Accessed**:
- `TCATBALF` - Transaction category balances (sequential input, sorted by account)
- `ACCOUNT-FILE` - Account master (random I-O for updates)
- `XREF-FILE` - Card cross-reference (random input, uses alternate key by account ID)
- `DISCGRP-FILE` - Disclosure group / interest rates (random input)
- `TRANSACT-FILE` - Transaction file (sequential output for interest transactions)

**Input Parameters**:
- `EXTERNAL-PARMS` - Contains processing date (PARM-DATE, 10 chars)
- Used in transaction ID generation

## Program Relationships

**Calls**: None

**Called By**: 
- JCL job INTCALC.jcl (or similar monthly interest calc job)
- Typically run monthly, after transaction posting, before statement generation

**Dependencies**:
- TCATBALF must be populated by CBTRN02C (transaction posting)
- DISCGRP must contain rate definitions for all account groups
- Runs after daily posting, before statements

## Notable Patterns

### Control Break Processing
- Classic COBOL control break pattern
- Tracks `WS-LAST-ACCT-NUM` to detect account change
- Uses `WS-FIRST-TIME` flag to skip update on first record
- Accumulates totals (`WS-TOTAL-INT`) per account
- Processes previous account when new account encountered

### Sequential + Random Access Mix
- TCATBAL read sequentially (main driver)
- ACCOUNT, XREF, DISCGRP accessed randomly (lookups)
- Efficient for processing all accounts while doing selective lookups

### Interest Rate Fallback
- First tries specific group/type/category combination
- If not found (status '23'): tries DEFAULT group
- Ensures all categories get some rate (even if generic)
- Flexible rate configuration

### Transaction ID Generation
- Combines processing date with incremental suffix
- Example: "2023-12-31" + "000001" = "2023-12-31000001"
- Ensures uniqueness across multiple interest transactions
- Date prefix groups interest transactions by period

### Cycle Reset Logic
- **Key insight**: Resets cycle credit/debit to zero
- Indicates this runs at **end of billing cycle**
- Prepares counters for next cycle's tracking
- Total balance maintained, but cycle-specific counters reset

### Missing Implementation
- `1400-COMPUTE-FEES` is stubbed (not implemented)
- Placeholder for future fee calculation logic
- Shows extensibility for adding fees alongside interest

### Alternate Key Usage (1110-GET-XREF-DATA)
- Reads XREF file by alternate key (account ID vs. primary card number)
- Uses `KEY IS FD-XREF-ACCT-ID` clause
- Gets card number for interest transaction generation
- Shows flexible file access patterns

### Generated Transaction Properties
- Type: '01' (debit/charge)
- Category: '05' (interest)
- Source: 'System'
- Merchant fields: Empty/zero (not applicable)
- Timestamps: Current date/time (both origin and processing)
- Card number: From XREF lookup

### Monthly Processing Indicator
- Formula divides by 1200 (12 months × 100)
- Indicates monthly interest calculation
- Would be 100 for annual, 365 for daily
- Confirms this is monthly cycle processing

### Zero-Rate Handling
- Checks `IF DIS-INT-RATE NOT = 0` before computing
- Skips interest/fee calculation for zero-rate categories
- Avoids generating unnecessary transactions
- Efficient processing
