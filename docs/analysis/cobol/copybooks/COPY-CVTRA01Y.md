# Copybook Analysis: CVTRA01Y

## Overview
**Source File**: `app/cpy/CVTRA01Y.cpy`
**Type**: Entity Record Definition
**Used By**: Transaction category balance programs (CBTRN03C, transaction reporting)
**Record Length**: 50 bytes

## Purpose
CVTRA01Y defines the transaction category balance record structure. This aggregates transaction amounts by account, transaction type, and category code, enabling reporting and analysis of spending patterns by category (e.g., groceries, gas, restaurants).

## Structure Overview
A compact 50-byte record with a compound key (account + type + category) and a balance field. This is a summary/aggregate table rather than individual transaction details.

## Key Fields

### Compound Key (TRAN-CAT-KEY)
- `TRANCAT-ACCT-ID` - Account identifier (11 digits)
- `TRANCAT-TYPE-CD` - Transaction type code (2 chars, likely "DB"=debit, "CR"=credit, "CA"=cash advance)
- `TRANCAT-CD` - Transaction category code (4 digits, e.g., 5411=groceries, 5812=restaurants)

### Balance
- `TRAN-CAT-BAL` - Accumulated balance for this account/type/category (S9(09)V99, signed with 2 decimals)

### Reserved Space
- `FILLER` - 22 bytes reserved (44% of record)

## Notable Patterns

### Hierarchical Key Structure
The compound key enables queries at multiple levels:
- All categories for an account
- All accounts for a category
- Specific account + type + category combination

### Category Codes
The 4-digit `TRANCAT-CD` likely follows Merchant Category Codes (MCC) standard used by credit card industry:
- 5411 - Grocery stores
- 5812 - Restaurants
- 5541 - Service stations (gas)
- 4111 - Transportation
- etc.

### Signed Balance
`S9(09)V99` allows negative balances (up to ±$9,999,999.99), supporting:
- Returns/refunds (negative amounts)
- Credits that offset debits
- Balance adjustments

### Small Record Size
At 50 bytes, this is very compact, allowing efficient storage and fast access for many category combinations.

## Usage Context

**Primary operations**:
- **Aggregate creation** - CBTRN03C batch job creates/updates category balances from transaction details
- **Reporting** - Programs read to generate spending analysis reports
- **Category summary** - Display spending by category on statements or online inquiry

**Business use cases**:
- Monthly statement breakdown by category
- Year-end summary for tax purposes
- Spending pattern analysis for fraud detection
- Budget tracking and alerts

**Relationship to other files**:
- Derived from transaction detail records (CVTRA02Y, CVTRA03Y, or similar)
- Links to accounts via TRANCAT-ACCT-ID
- One record per unique account + type + category combination

**Update pattern**:
- Likely updated by batch job (CBTRN03C) after transaction posting
- Read-mostly during online inquiry and reporting
- May be rebuilt periodically from transaction history
