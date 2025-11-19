# Program Analysis: CSUTLDTC

## Overview
**Source File**: `app/cbl/CSUTLDTC.cbl`
**Type**: Utility Subprogram
**Module**: Utilities

## Business Purpose
CSUTLDTC is a date validation utility that validates dates by calling the IBM Language Environment CEEDAYS API. It checks if a date string is valid according to a specified format mask and returns a success/failure message. This provides centralized, consistent date validation across the CardDemo application.

## Key Logic

### Date Validation Process
1. Receives date string and format mask as input parameters
2. Prepares variable-length strings for CEEDAYS API (IBM LE standard)
3. Calls CEEDAYS to convert date to Lilian format (days since Oct 15, 1582)
4. Interprets feedback code from CEEDAYS
5. Returns validation result message and severity code

### Validation Results
Maps CEEDAYS feedback codes to readable messages:
- **FC-INVALID-DATE** → "Date is valid" (confusing: actually means no error)
- **FC-BAD-DATE-VALUE** → "Datevalue error"
- **FC-INVALID-MONTH** → "Invalid month"
- **FC-NON-NUMERIC-DATA** → "Nonnumeric data"
- **FC-INSUFFICIENT-DATA** → "Insufficient"
- Other error codes handled with specific messages
- Default: "Date is invalid"

### Return Code
Sets RETURN-CODE to severity level from CEEDAYS (0 = success, non-zero = error).

## Data Dependencies

**Key Copybooks**:
- `CSUTLDPY.cpy` - Likely contains parameter definitions (not shown in this listing)
- `CSUTLDWY.cpy` - Likely contains working storage structures (not shown in this listing)

**External Calls**:
- `CEEDAYS` - IBM Language Environment date conversion API

**Parameters** (Linkage Section):
- `LS-DATE` - Input: date to validate (10 chars)
- `LS-DATE-FORMAT` - Input: format mask (10 chars, e.g., "YYYY-MM-DD")
- `LS-RESULT` - Output: validation result message (80 chars)

## Program Relationships

**Called By**: Any program needing date validation
- Account programs (date field validation)
- Transaction programs (transaction date checks)
- Customer programs (DOB validation)
- Online and batch programs

**Calls**: 
- CEEDAYS (IBM Language Environment API)

## Notable Patterns

### Variable-Length String Handling
Uses COBOL OCCURS DEPENDING ON for variable-length strings compatible with IBM LE APIs:
```cobol
02 Vstring-text.
   03 Vstring-char PIC X
       OCCURS 0 TO 256 TIMES
       DEPENDING ON Vstring-length
```

### Feedback Code Analysis
Comprehensive condition names (88-levels) for all possible CEEDAYS error conditions, enabling readable error handling.

### Reusable Utility
Designed as a called subrogram (not CICS program), can be used by both:
- CICS online programs (via CALL)
- Batch programs (via CALL)

### Lilian Date Format
CEEDAYS converts to Lilian date (integer days since Oct 15, 1582), useful for:
- Date arithmetic (add/subtract days)
- Date comparison
- Age calculations

### Error Message Note
There's a logic issue: `FC-INVALID-DATE` (which actually means success/valid date) returns "Date is valid", but the condition name is misleading. The EVALUATE should likely check for zero feedback token first.

## Migration Considerations

**Modern .NET equivalent**:
- Replace CEEDAYS with DateTime.TryParseExact()
- Simplify error handling with built-in exception messages
- Consider standardizing on ISO 8601 date format

**Testing focus**:
- Validate error messages match expected behavior
- Test various date formats (YYYY-MM-DD, MM/DD/YYYY, etc.)
- Test boundary conditions (leap years, month boundaries)
- Verify feedback code interpretation
