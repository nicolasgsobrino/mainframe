# Copybook Analysis: CUSTREC

## Overview
**Source File**: `app/cpy/CUSTREC.cpy`
**Type**: Entity Record Definition
**Used By**: Customer-related programs (CBCUS01C, customer inquiry/update programs)
**Record Length**: 500 bytes

## Purpose
CUSTREC defines the complete customer master record structure stored in the customer VSAM file. This is the core entity representing a cardholder in the CardDemo system, containing personal information, contact details, and credit profile data.

## Structure Overview
A flat 500-byte record containing customer identification, personal information, address, contact details, and financial/credit information. The structure maps directly to the VSAM customer master file layout.

## Key Fields

### Identification
- `CUST-ID` - Unique customer identifier (9 digits, primary key)
- `CUST-SSN` - Social Security Number (9 digits, PII)
- `CUST-GOVT-ISSUED-ID` - Government ID number (20 chars, passport/license)

### Personal Information
- `CUST-FIRST-NAME` - First name (25 chars)
- `CUST-MIDDLE-NAME` - Middle name (25 chars)
- `CUST-LAST-NAME` - Last name (25 chars)
- `CUST-DOB-YYYYMMDD` - Date of birth in YYYY-MM-DD format (10 chars)

### Address (Multi-line with state/country/zip)
- `CUST-ADDR-LINE-1/2/3` - Three address lines (50 chars each)
- `CUST-ADDR-STATE-CD` - State code (2 chars, e.g., "TX")
- `CUST-ADDR-COUNTRY-CD` - Country code (3 chars, e.g., "USA")
- `CUST-ADDR-ZIP` - Postal/ZIP code (10 chars)

### Contact
- `CUST-PHONE-NUM-1` - Primary phone (15 chars)
- `CUST-PHONE-NUM-2` - Secondary phone (15 chars)

### Financial/Credit Profile
- `CUST-FICO-CREDIT-SCORE` - FICO credit score (3 digits, 300-850)
- `CUST-EFT-ACCOUNT-ID` - Electronic Funds Transfer account (10 chars)
- `CUST-PRI-CARD-HOLDER-IND` - Primary cardholder indicator (1 char, Y/N)

### Reserved Space
- `FILLER` - 168 bytes reserved for future expansion

## Notable Patterns

### Fixed-Length Record
500-byte fixed record length typical of VSAM KSDS (Key-Sequenced Data Set) files - ensures predictable I/O and indexing.

### PII Data Protection
Contains multiple PII (Personally Identifiable Information) fields requiring secure handling:
- SSN, DOB, address, phone numbers, government ID

### Flexible Address Format
Three address lines provide flexibility for international addresses and complex address formats.

### Future Expansion
168 bytes of FILLER (33.6% of record) allows for future fields without file reorganization.

## Usage Context

**Primary operations**:
- Customer creation/registration (batch import or online add)
- Customer inquiry by ID (display customer details)
- Customer update (address changes, phone updates)
- Credit score lookup for transaction authorization

**Business relationships**:
- Parent entity for accounts (one customer → many accounts)
- Used for identity verification during sign-on
- Credit score influences transaction limits and approvals

**VSAM file organization**:
- Likely keyed by CUST-ID (primary key)
- May have alternate index on SSN for lookup
