# Program Analysis: COMEN01C

## Overview
**Source File**: `app/cbl/COMEN01C.cbl`
**Type**: Online Transaction Program (CICS)
**Module**: Menu/Navigation
**Transaction ID**: CM00

## Business Purpose
COMEN01C is the main menu for regular users in the CardDemo application. It presents a numbered menu of available functions (11 options) and routes users to the selected program. The menu acts as a navigation hub, providing access to account management, card management, transaction viewing, reporting, and bill payment features.

## Key Logic

### Initial Entry (First Display)
When XCTL'd from COSGN00C:
1. Check if re-entering (CDEMO-PGM-CONTEXT)
2. If first entry, set re-enter flag and display menu
3. Initialize screen with LOW-VALUES
4. Build menu options dynamically from COMEN02Y copybook
5. Display menu screen

### Menu Selection Processing (ENTER key)
1. Receive user's option number (1-11)
2. Validate numeric and within range
3. Check authorization (user type vs. required type)
4. Evaluate selected option:
   - **COPAUS0C** (option 11): Check if program is installed first
   - **DUMMY programs**: Display "coming soon" message
   - **All others**: XCTL to the selected program with COMMAREA

### Authorization Check
- Each menu option has a user type requirement ('U'=User, 'A'=Admin)
- Regular users blocked from admin-only options
- Error message: "No access - Admin Only option..."

### Error Handling
- Non-numeric option → "Please enter a valid option number..."
- Out of range (0 or > 11) → "Please enter a valid option number..."
- Program not installed → "This option [name] is not installed..."
- DUMMY program → "This option [name] is coming soon ..." (green message)
- Invalid function key → "Invalid key pressed..."

### F3 Key Processing
Returns to sign-on screen (COSGN00C).

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - COMMAREA (navigation context)
- `COMEN02Y` - Menu options table (11 options with names, programs, access levels)
- `COMEN01` - BMS screen map
- `CSDAT01Y` - Date/time structures
- `CSMSG01Y` - Common messages
- `COTTL01Y` - Title definitions

**Screens** (BMS):
- `COMEN1A` (mapset COMEN01) - Main menu screen

## Program Relationships

**Called By (XCTL)**:
- `COSGN00C` - Sign-on program (after successful authentication)
- Any program that returns to main menu

**Calls (XCTL)** (based on user selection):
1. `COACTVWC` - Account View
2. `COACTUPC` - Account Update
3. `COCRDLIC` - Credit Card List
4. `COCRDSLC` - Credit Card View
5. `COCRDUPC` - Credit Card Update
6. `COTRN00C` - Transaction List
7. `COTRN01C` - Transaction View
8. `COTRN02C` - Transaction Add
9. `CORPT00C` - Transaction Reports
10. `COBIL00C` - Bill Payment
11. `COPAUS0C` - Pending Authorization View (if installed)
- `COSGN00C` - Return to sign-on (F3)

## Notable Patterns

### Data-Driven Menu
Menu options stored in copybook (COMEN02Y), not hardcoded:
- Easy to add/remove options
- Consistent structure (number, name, program, access level)
- Menu displayed by looping through array

### Dynamic Menu Building
`BUILD-MENU-OPTIONS` paragraph constructs menu text:
```cobol
STRING option-number '. ' option-name INTO display-field
```
Result: "1. Account View", "2. Account Update", etc.

### Program Availability Check
For COPAUS0C, uses CICS INQUIRE PROGRAM to verify installation before XCTL:
- If installed: proceed with XCTL
- If not: display error message
This pattern could apply to other optional features.

### User Type Authorization
Each option tagged with required user type ('U' or 'A'):
- Regular users (CDEMO-USRTYP-USER) blocked from 'A' options
- Admin users have access to all options
- Authorization check before XCTL

### Pseudo-Conversational Flow
Standard CICS pattern:
- First time: display menu
- Re-enter: process selection or function key
- RETURN with TRANSID to maintain conversation

### Coming Soon Placeholder
Options can be marked with 'DUMMY' prefix in program name:
- Displays green message "coming soon"
- Allows menu structure to be defined before implementation
- Better UX than removing options entirely

### Context Preservation
Updates COMMAREA before each XCTL:
- FROM-TRANID and FROM-PROGRAM (for return navigation)
- PGM-CONTEXT reset to ENTER (0) for fresh entry
- USER-ID and USER-TYPE carried forward

## Menu Options Summary

All 11 options accessible to regular users ('U'):

| # | Option Name | Program | Function |
|---|-------------|---------|----------|
| 1 | Account View | COACTVWC | View account details |
| 2 | Account Update | COACTUPC | Modify account information |
| 3 | Credit Card List | COCRDLIC | List cards for account |
| 4 | Credit Card View | COCRDSLC | View card details |
| 5 | Credit Card Update | COCRDUPC | Modify card information |
| 6 | Transaction List | COTRN00C | Browse transactions |
| 7 | Transaction View | COTRN01C | View transaction details |
| 8 | Transaction Add | COTRN02C | Add new transaction |
| 9 | Transaction Reports | CORPT00C | Run transaction reports |
| 10 | Bill Payment | COBIL00C | Make bill payments |
| 11 | Pending Authorization | COPAUS0C | View pending auths (optional) |

## Migration Considerations

**Modern web equivalent**:
- Replace with dashboard or navigation sidebar
- RESTful API endpoints for each menu option
- Role-based menu rendering (hide unauthorized options)
- Breadcrumb navigation
- Quick action tiles/cards
- Search functionality for menu options

**Navigation patterns**:
- SPA routing (React Router, Angular Router, etc.)
- Menu state managed by frontend framework
- Backend API for authorization checks
- Dynamic menu loading from configuration/database

**User experience**:
- Visual icons for each menu option
- Recent actions / favorites
- Keyboard shortcuts
- Responsive design for mobile
- Help text / tooltips for each option
