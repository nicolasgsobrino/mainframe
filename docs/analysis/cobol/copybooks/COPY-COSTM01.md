# Copybook Analysis: COSTM01

## Overview
**Source File**: `app/cpy/COSTM01.CPY`  
**Type**: Data Structure  
**Used By**: Statement generation programs (CBSTM03A, CBSTM03B)

## Purpose
Defines the transaction record layout specifically formatted for statement reporting. This is an alternate view of transaction data optimized for customer-facing statements rather than internal processing.

## Structure Overview
Modified transaction record that separates key fields from detail data to support statement generation indexing and sorting patterns.

## Key Fields

**Transaction Key** (32 bytes):
- `TRNX-CARD-NUM` (16 bytes) - Card number (primary sort key)
- `TRNX-ID` (16 bytes) - Transaction ID (secondary sort key)

**Transaction Details** (318 bytes - TRNX-REST):
- `TRNX-TYPE-CD` (2 bytes) - Transaction type code
- `TRNX-CAT-CD` (4 digits) - Transaction category code
- `TRNX-SOURCE` (10 bytes) - Transaction source system
- `TRNX-DESC` (100 bytes) - Transaction description (for statement)
- `TRNX-AMT` (S9(9)V99) - Transaction amount (signed, 2 decimals)
- `TRNX-MERCHANT-ID` (9 digits) - Merchant identifier
- `TRNX-MERCHANT-NAME` (50 bytes) - Merchant name (for statement)
- `TRNX-MERCHANT-CITY` (50 bytes) - Merchant city (for statement)
- `TRNX-MERCHANT-ZIP` (10 bytes) - Merchant ZIP code
- `TRNX-ORIG-TS` (26 bytes) - Original transaction timestamp
- `TRNX-PROC-TS` (26 bytes) - Processing timestamp
- Filler (20 bytes) - Reserved for future use

## Notable Patterns

### Two-Part Key Structure
Record split into TRNX-KEY and TRNX-REST allows programs to:
1. Index or sort by card number first, then transaction ID
2. Load key separately from detail for memory efficiency
3. Support indexed file organization with composite key

### Statement-Oriented Fields
Unlike operational transaction records, this layout emphasizes:
- Extended description field (100 bytes for customer clarity)
- Merchant name, city, zip for statement detail
- Separate timestamps for audit trail on statements

### 2D Array Storage
CBSTM03A loads this structure into a 51×10 array:
- 51 different cards
- Up to 10 transactions per card
- TRNX-KEY separates card identification from transaction data
- TRNX-REST (318 bytes) stored as single unit per transaction

## Usage Context
This copybook is specifically for statement reporting batch processing. Programs read transaction file using this layout, organize by card/account, and generate customer statements with transaction details formatted for readability.

## Relationship to Other Copybooks
- Alternative to `CVTRA05Y` (operational transaction layout)
- Used in conjunction with `CVACT03Y` (cross-reference) to map cards to accounts
- Customer/account data comes from separate copybooks (CUSTREC, CVACT01Y)
