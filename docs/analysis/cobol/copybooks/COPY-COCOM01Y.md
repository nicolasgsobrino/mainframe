# Copybook Analysis: COCOM01Y

## Overview
**Source File**: `app/cpy/COCOM01Y.cpy`
**Type**: Communication Area (COMMAREA)
**Used By**: All online programs (17+ programs)

## Purpose
COCOM01Y defines the common communication area (`CARDDEMO-COMMAREA`) that is passed between all CICS online programs in the CardDemo application. This is the primary mechanism for maintaining session state and passing data between programs as users navigate through the application.

## Structure Overview
The communication area is a 186-byte structure divided into five logical sections:
1. **General Info** - Navigation and user context (38 bytes)
2. **Customer Info** - Current customer data (84 bytes)
3. **Account Info** - Current account data (12 bytes)
4. **Card Info** - Current card data (16 bytes)
5. **More Info** - Screen navigation context (14 bytes)

This structure represents the complete session state that follows a user through their interaction with the CardDemo application.

## Key Fields

### Navigation Context
- `CDEMO-FROM-TRANID` / `CDEMO-FROM-PROGRAM` - Source transaction/program (for navigation back)
- `CDEMO-TO-TRANID` / `CDEMO-TO-PROGRAM` - Target transaction/program (for navigation forward)
- `CDEMO-PGM-CONTEXT` - Indicates if program is entering fresh (0) or re-entering (1)
- `CDEMO-LAST-MAP` / `CDEMO-LAST-MAPSET` - Screen navigation state

### User Session
- `CDEMO-USER-ID` - Authenticated user identifier (8 characters)
- `CDEMO-USER-TYPE` - User role: 'A' (Admin) or 'U' (User)
  - Controls access to administrative functions

### Current Business Context
- `CDEMO-CUST-ID` - Customer being viewed/edited (9 digits)
- `CDEMO-CUST-FNAME/MNAME/LNAME` - Customer name fields (for display)
- `CDEMO-ACCT-ID` - Account being processed (11 digits)
- `CDEMO-ACCT-STATUS` - Account status indicator
- `CDEMO-CARD-NUM` - Card number being processed (16 digits)

## Notable Patterns

### Condition Names (88-levels)
Uses COBOL 88-level condition names for readable code:
- `CDEMO-USRTYP-ADMIN` / `CDEMO-USRTYP-USER` - Type checking
- `CDEMO-PGM-ENTER` / `CDEMO-PGM-REENTER` - Context checking

### Navigation Pattern
The FROM/TO transaction and program fields enable:
- Forward navigation (where to go next)
- Backward navigation (return to previous screen)
- Program chain tracking for error recovery

### Multi-tier Context
Stores customer → account → card hierarchy, allowing programs to:
- Display context breadcrumbs
- Validate relationships between entities
- Pre-populate related data on screens

## Usage Context

**Critical for all online programs**:
- Passed via CICS COMMAREA on every XCTL and RETURN
- Programs read to determine re-entry vs. fresh entry
- Programs update to pass context to next program
- Maintains user session identity and permissions
- Preserves business context across screen transitions

**Session lifecycle**:
1. Sign-on program (COSGN00C) initializes after authentication
2. Each program reads, uses, and updates as needed
3. Communication area carries state until user signs off

**Size constraint**: Must be ≤ 32KB (CICS COMMAREA limit), currently 186 bytes
