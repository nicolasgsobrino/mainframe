# Copybook Analysis: CVACT01Y

## Overview
**Source File**: `app/cpy/CVACT01Y.cpy`
**Type**: Entity Record Definition
**Used By**: Account programs (CBACT01C-04C, COACTVWC, COACTUPC)
**Record Length**: 300 bytes

## Purpose
CVACT01Y defines the account master record structure representing a credit card account. This is a core entity that tracks account status, credit limits, current balances, and billing cycle activity.

## Structure Overview
A 300-byte fixed-length record containing account identification, status, financial balances, credit limits, date tracking, and billing cycle information. Maps directly to the VSAM account file.

## Key Fields

### Identification & Status
- `ACCT-ID` - Unique account identifier (11 digits, primary key)
- `ACCT-ACTIVE-STATUS` - Account active/inactive indicator (1 char, Y/N or A/I)
- `ACCT-GROUP-ID` - Group/corporate account identifier (10 chars)

### Financial Balances (signed, 2 decimal places)
- `ACCT-CURR-BAL` - Current account balance (S9(10)V99, up to $99,999,999.99)
- `ACCT-CREDIT-LIMIT` - Total credit limit (S9(10)V99)
- `ACCT-CASH-CREDIT-LIMIT` - Cash advance limit (S9(10)V99, subset of total limit)

### Billing Cycle Activity
- `ACCT-CURR-CYC-CREDIT` - Total credits this billing cycle (S9(10)V99)
- `ACCT-CURR-CYC-DEBIT` - Total debits this billing cycle (S9(10)V99)

### Date Tracking
- `ACCT-OPEN-DATE` - Account opening date (10 chars, YYYY-MM-DD format)
- `ACCT-EXPIRAION-DATE` - Expiration date (10 chars, note typo in field name)
- `ACCT-REISSUE-DATE` - Card reissue date (10 chars)

### Geographic & Grouping
- `ACCT-ADDR-ZIP` - Billing address ZIP code (10 chars)
- `ACCT-GROUP-ID` - Corporate or group account ID (10 chars)

### Reserved Space
- `FILLER` - 178 bytes reserved for future expansion

## Notable Patterns

### Signed Monetary Fields
Uses `S9(10)V99` (signed, 2 decimals) for all financial amounts:
- Allows negative balances (credits exceed debits)
- Supports standard currency calculations
- Range: -$99,999,999.99 to +$99,999,999.99

### Dual Credit Limits
Separate limits for total credit and cash advances reflects real-world credit card business rules where cash advances typically have lower limits.

### Billing Cycle Tracking
Current cycle credit/debit totals enable:
- Statement generation (calculate monthly activity)
- Interest calculation (based on daily balance changes)
- Minimum payment computation

### Future Expansion
178 bytes of FILLER (59% of record) allows significant future enhancement without file reorganization.

## Usage Context

**Primary operations**:
- Account inquiry (view balance, limits, dates)
- Account updates (status changes, limit adjustments)
- Transaction posting (update balance and cycle totals)
- Interest calculation (monthly batch process, CBACT04C)
- Statement generation (monthly billing)

**Business relationships**:
- Linked to customer (many accounts per customer)
- Parent to cards (one account → many cards)
- Parent to transactions (posted against account balance)

**Validation rules**:
- Current balance ≤ credit limit
- Cash credit limit ≤ total credit limit
- Cycle debits + cycle credits = balance change
- Account must be active for new transactions

**Typo note**: `ACCT-EXPIRAION-DATE` has spelling error (missing T), should be preserved in migration for compatibility.
