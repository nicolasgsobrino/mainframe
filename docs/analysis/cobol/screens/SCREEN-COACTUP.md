# Screen Analysis: COACTUP

## Overview
**Source File**: `app/bms/COACTUP.bms`
**Type**: Comprehensive Data Entry and Update
**Program**: COACTUPC (Account Update)
**Map Name**: CACTUPA

## Purpose
Provides a comprehensive interface for updating both account information and associated customer details in a single integrated screen. This is one of the most complex screens in the CardDemo application, combining account management and customer data maintenance. Users can modify account attributes (credit limits, dates, status) along with customer personal information (name, address, contact details).

## Screen Layout (24x80)

### Header Section (Lines 1-2)
- Transaction name (TRNNAME)
- Screen titles (TITLE01/TITLE02)
- Current date and time
- Program name (PGMNAME)

### Title and Identification (Lines 4-5)
**Title**: "Update Account" (line 4, centered)

**Key Fields** (Line 5):
- `ACCTSID` (11 chars) - Account Number
  - Initial cursor position (IC attribute)
  - Primary key field
  - Underlined input field
  
- `ACSTTUS` (1 char) - Account Active Y/N
  - Y = Active, N = Inactive
  - Underlined input field

### Account Information Section (Lines 6-10)

**Date Fields** (Lines 6-8) - Format: YYYY-MM-DD:
- **Opened** (line 6): `OPNYEAR` (4), `OPNMON` (2), `OPNDAY` (2)
- **Expiry** (line 7): `EXPYEAR` (4), `EXPMON` (2), `EXPDAY` (2)
- **Reissue** (line 8): `RISYEAR` (4), `RISMON` (2), `RISDAY` (2)

All date fields:
- Right-justified
- Underlined
- Separate fields for year, month, day with hyphen separators

**Financial Fields** (Lines 6-10) - Currency format:
- `ACRDLIM` (15 chars, line 6) - Credit Limit
  - Formatted currency input
  - Right-aligned
  
- `ACSHLIM` (15 chars, line 7) - Cash Credit Limit
  - Formatted currency input
  - Right-aligned
  
- `ACURBAL` (15 chars, line 8) - Current Balance
  - Formatted currency input
  - Right-aligned
  
- `ACRCYCR` (15 chars, line 9) - Current Cycle Credit
  - Formatted currency input
  - Right-aligned
  
- `ACRCYDB` (15 chars, line 10) - Current Cycle Debit
  - Formatted currency input
  - Right-aligned

**Account Group** (Line 10):
- `AADDGRP` (10 chars) - Account Group identifier

### Customer Details Section (Lines 11-20)
**Section Title**: "Customer Details" (line 11, centered)

**Customer Identification** (Lines 12-13):
- `ACSTNUM` (9 chars, line 12) - Customer ID
  - Numeric field
  - Links to CUSTDAT file
  
- **Social Security Number** (line 12) - Three separate fields:
  - `ACTSSN1` (3 chars) - First segment
  - `ACTSSN2` (2 chars) - Middle segment
  - `ACTSSN3` (4 chars) - Last segment
  - Format: XXX-XX-XXXX
  - Pre-populated with "999-99-9999" pattern
  
- **Date of Birth** (line 13):
  - `DOBYEAR` (4 chars), `DOBMON` (2 chars), `DOBDAY` (2 chars)
  - Format: YYYY-MM-DD
  - Right-justified
  
- `ACSTFCO` (3 chars, line 13) - FICO Score
  - Numeric, 300-850 range typically

**Name Fields** (Lines 14-15):
- `ACSFNAM` (25 chars) - First Name
- `ACSMNAM` (25 chars) - Middle Name
- `ACSLNAM` (25 chars) - Last Name

All name fields displayed side-by-side, underlined, editable.

**Address Fields** (Lines 16-18):
- `ACSADL1` (50 chars, line 16) - Address Line 1
- `ACSADL2` (50 chars, line 17) - Address Line 2
- `ACSCITY` (50 chars, line 18) - City
- `ACSSTTE` (2 chars, line 16) - State (US state code)
- `ACSZIPC` (5 chars, line 17) - ZIP Code
- `ACSCTRY` (3 chars, line 18) - Country (3-letter code)

**Contact Information** (Lines 19-20):
- **Phone 1** (line 19): `ACSPH1A` (3), `ACSPH1B` (3), `ACSPH1C` (4)
  - Format: AAA-BBB-CCCC (US phone format)
  - Right-justified numeric fields
  
- **Phone 2** (line 20): `ACSPH2A` (3), `ACSPH2B` (3), `ACSPH2C` (4)
  - Secondary phone number
  - Same format as Phone 1
  
- `ACSGOVT` (20 chars, line 19) - Government Issued ID Reference
- `ACSEFTC` (10 chars, line 20) - EFT Account ID
- `ACSPFLG` (1 char, line 20) - Primary Card Holder Y/N

### Message Areas (Lines 22-23)
- `INFOMSG` (45 chars, line 22) - Informational messages
- `ERRMSG` (78 chars, line 23) - Error messages in red, bright

### Navigation Footer (Line 24)
**Primary Keys** (FKEYS, visible):
- **ENTER** - Process (validate changes)
- **F3** - Exit (cancel and return)

**Confirmation Keys** (FKEY05, FKEY12, initially hidden):
- **F5** - Save (commit changes)
- **F12** - Cancel (discard changes)

## Function Keys

### Primary Operations
- **F3**: Exit - Cancel and return to calling program without saving
- **Enter**: Process - Validate all fields and prepare for confirmation

### Confirmation Operations (After Validation)
- **F5**: Save - Commit account and customer changes to database files
- **F12**: Cancel - Discard changes and return to edit mode or exit

## Field Organization Summary

### Total Field Count: 40+ editable fields

**Account Fields (12)**:
- Account number, status
- 3 date sets (opened, expiry, reissue) = 9 fields
- Account group

**Financial Fields (5)**:
- Credit limit, cash credit limit, current balance, cycle credit, cycle debit

**Customer ID Fields (5)**:
- Customer number, SSN (3 parts), FICO score

**Date Fields (3)**:
- Date of birth (year, month, day)

**Name Fields (3)**:
- First, middle, last name

**Address Fields (6)**:
- Address lines 1-2, city, state, ZIP, country

**Contact Fields (9)**:
- Phone 1 (3 parts), Phone 2 (3 parts), government ID, EFT account, primary flag

## Workflow Steps

### Step 1: Initial Display
- User enters account number
- Program reads ACCTDAT and CUSTDAT files
- Screen displays with current values pre-populated
- All editable fields unlocked

### Step 2: User Modifications
- User can modify any editable field
- Cursor moves between fields using Tab or Enter
- Real-time field-level editing

### Step 3: Validation (Enter pressed)
- Comprehensive validation of all modified fields
- Date validations (valid dates, logical relationships)
- Financial field validations (numeric, formatted correctly)
- Name validations (alphabetic)
- Address validations (state codes, ZIP format)
- Phone validations (numeric, proper format)
- If any validation fails: error message, cursor positioned at error field
- If all pass: confirmation message, F5/F12 revealed

### Step 4: Confirmation
- F5: Save changes to both ACCTDAT and CUSTDAT files
- F12: Cancel and discard all changes
- F3: Exit without saving

## Navigation Flow

**Entry Points**:
- From account list/search screen
- Direct transaction invocation with account number
- COMMAREA contains account ID

**Exit Points**:
- F3 (any time) → Return to previous screen
- F12 (after validation) → Return to edit or previous screen
- F5 (after validation) → Save and return with success message

## Validation Rules (Summary)

### Account Validations
- Account number: Must exist in ACCTDAT
- Status: Must be 'Y' or 'N'
- Dates: Must be valid calendar dates
- Date logic: Expiry >= Opened, Reissue >= Opened
- Financial fields: Must be numeric, properly formatted currency
- Credit limit: Must be >= current balance
- Cycle credit/debit: Must be <= credit limit

### Customer Validations
- Customer ID: Must exist in CUSTDAT, must match account's customer reference
- SSN: Must be 9 digits (validated as 3-2-4 pattern)
- DOB: Valid date, customer must be 18+ years old
- FICO Score: Typically 300-850 range
- Names: Alphabetic characters and spaces, cannot be blank
- State: Must be valid US state code (2 chars)
- ZIP: Must be 5 numeric digits
- Phone: Must be 10 numeric digits (3-3-4 pattern)
- Country: Valid 3-letter country code (USA, CAN, etc.)

## Technical Characteristics

### Complexity Indicators
- **Field Count**: 40+ editable fields
- **Data Sources**: Two primary files (ACCTDAT, CUSTDAT)
- **Validation Rules**: 30+ distinct validation checks
- **Screen Density**: High (most of 24 lines used for data)
- **State Management**: Complex state tracking across pseudo-conversations

### Display Attributes
- Extensive use of color coding for organization
- Careful field positioning for logical grouping
- Right-justification for numeric/date fields
- Underlines for input fields to guide user
- Hidden fields become visible in confirmation mode

### Field Protection Strategy
- Initial entry: Account number unprot, all others prot until record loaded
- After load: All data fields unprot for editing
- Confirmation keys initially dark (hidden), revealed after successful validation

## Modernization Considerations

### Modern UI Equivalent
This single 24x80 screen would typically be split into multiple modern UI sections:

1. **Account Details Tab/Section**:
   - Account number (read-only after load)
   - Status toggle
   - Date pickers (opened, expiry, reissue)
   - Financial fields with currency formatting
   - Account group dropdown

2. **Customer Details Tab/Section**:
   - Customer ID (lookup with autocomplete)
   - Personal info (name, DOB, SSN - masked)
   - FICO score display

3. **Address Tab/Section**:
   - Address form with validation
   - City, state, ZIP, country
   - Address verification integration

4. **Contact Tab/Section**:
   - Phone numbers with formatting
   - EFT account
   - Government ID
   - Primary cardholder flag

### UI/UX Improvements
- **Tabbed Interface**: Split into logical tabs to reduce cognitive load
- **Sectioned Layout**: Group related fields with visual separators
- **Smart Defaults**: Pre-populate common values
- **Autocomplete**: Customer lookup, city/state/ZIP lookup
- **Inline Validation**: Real-time feedback as user types
- **Currency Formatting**: Auto-format as user types ($12,345.67)
- **Date Pickers**: Calendar widgets for all date fields
- **Phone Formatting**: Auto-format phone numbers (800) 555-1234
- **SSN Masking**: Show as ***-**-1234, full value only on explicit reveal
- **Address Verification**: Integration with USPS or similar service
- **Change Tracking**: Highlight modified fields, show original vs new values
- **Save Confirmation**: Modal dialog: "Save changes to account 00012345678?"
- **Field-Level Help**: Tooltips explaining validation rules

### Responsive Design
- **Desktop**: Two-column layout with logical grouping
- **Tablet**: Single column with collapsible sections
- **Mobile**: Wizard-style multi-step form (Account → Customer → Address → Contact)

### API Design
Rather than single monolithic update, consider separate endpoints:

```
PATCH /api/accounts/{accountId}  
PATCH /api/customers/{customerId}
PUT /api/accounts/{accountId}/customer/{customerId}  (link update)
```

Or comprehensive single endpoint with partial update support:
```
PATCH /api/accounts/{accountId}/full
```

Request body allows selective updates (only send changed fields):
```json
{
  "account": {
    "status": "Y",
    "creditLimit": 10000.00,
    "expiryDate": "2025-12-31"
  },
  "customer": {
    "firstName": "John",
    "lastName": "Smith",
    "phone1": "8005551234"
  }
}
```

### Performance Optimization
- Load account and customer data in parallel
- Cache customer data for account (reduce database reads)
- Debounce validation (don't validate on every keystroke)
- Optimistic UI updates
- Background save with progress indicator

### Security Considerations
- **PII Protection**: SSN, DOB, phone numbers are sensitive - audit all access
- **Field-Level Security**: Some users can view but not edit certain fields (FICO, financial limits)
- **Audit Trail**: Log all changes with before/after values, user, timestamp
- **Authorization**: Verify user has permission to update this account
- **Data Masking**: Mask SSN in display, logs, and audit trails

### Testing Strategy
- **Unit Tests**: Validation logic for each field type
- **Integration Tests**: Database updates to ACCTDAT and CUSTDAT
- **UI Tests**: Form submission, error handling, field navigation
- **Validation Tests**: All 30+ validation rules
- **Concurrency Tests**: Simultaneous updates to same account
- **Performance Tests**: Form load time, save time with large customer base
- **Accessibility Tests**: Screen reader support, keyboard navigation
