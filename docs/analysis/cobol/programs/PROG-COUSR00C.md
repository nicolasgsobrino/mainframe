# Program Analysis: COUSR00C

## Overview
**Source File**: `app/cbl/COUSR00C.cbl`  
**Type**: Online Transaction  
**Module**: User Management  
**Transaction ID**: CU00  
**Screen**: COUSR00

## Business Purpose
Provides a paginated list of all users in the system. Allows administrators to browse users, search by user ID, and select users for update or deletion. Supports forward/backward navigation through user list with 10 users displayed per page.

## Key Logic

### List Display
- Displays up to 10 users per screen
- Shows user ID, first name, last name, and user type for each user
- Maintains current page number
- Tracks first and last user IDs on current page for pagination

### Search Capability
- Optional user ID search field filters starting point in list
- Starts browse from specified user ID or beginning of file
- Case-sensitive user ID matching

### Selection Actions
User can enter action code in selection column:
- **U** - Update selected user (XCTLs to COUSR02C)
- **D** - Delete selected user (XCTLs to COUSR03C)

### Pagination Logic
- **PF7 (Backward)**: Navigate to previous page
- **PF8 (Forward)**: Navigate to next page
- Uses STARTBR/READNEXT/READPREV/ENDBR for file traversal
- Prevents navigation beyond file boundaries with appropriate messages

### Browse Management
1. STARTBR positions file pointer at specified user ID
2. READNEXT populates forward through file
3. READPREV populates backward through file
4. Tracks EOF conditions to disable further navigation
5. ENDBR closes browse after page load

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - Communication area with custom CU00 extension
- `CSUSR01Y` - User security data structure
- `COTTL01Y` - Screen title definitions
- `CSDAT01Y` - Date/time structures
- `CSMSG01Y` - Message definitions

**Files Accessed**:
- `USRSEC` - User security file (KSDS VSAM file, browsed by user ID)

**Screens**:
- `COUSR00` - User list screen (BMS map COUSR0A)

## Program Relationships

**Called By**: 
- `COADM01C` - Admin menu

**Calls**: 
- `COUSR02C` - User update program (when U selected)
- `COUSR03C` - User delete program (when D selected)

**Navigation**:
- PF3 returns to admin menu
- PF7 scrolls backward
- PF8 scrolls forward
- Enter processes selection or search

## Notable Patterns

### Bidirectional Browse
Handles both forward (READNEXT) and backward (READPREV) file traversal:
```
READNEXT: Populates rows 1-10 forward
READPREV: Populates rows 10-1 backward (reverse order)
```

### Page State Management
Commarea extension tracks:
- First user ID on page
- Last user ID on page
- Current page number
- Next page available flag
- Selected user and action

### Dynamic Row Population
Uses EVALUATE/WHEN to populate specific screen rows based on index:
```cobol
EVALUATE WS-IDX
  WHEN 1 MOVE ... TO USRID01I
  WHEN 2 MOVE ... TO USRID02I
  ...
  WHEN 10 MOVE ... TO USRID10I
END-EVALUATE
```

### Selection Processing
Checks all 10 selection fields (SEL0001I through SEL0010I) to determine user action. Validates selection code and corresponding user ID before XCTLing to appropriate program.

### Boundary Detection
Tracks when at top or bottom of file:
- ENDFILE condition sets USER-SEC-EOF flag
- Displays informative messages ("at top of page", "at bottom of page")
- Prevents unnecessary browse operations

### Screen Refresh Strategy
Uses conditional ERASE on SEND:
- SEND-ERASE-YES: Full screen refresh (initial display, error conditions)
- SEND-ERASE-NO: Partial refresh (boundary messages only)

## Error Handling
- NOTFND on STARTBR: User positioned beyond file, message displayed
- ENDFILE on READNEXT/READPREV: End of data reached, pagination disabled
- Invalid selection code: Error message, cursor positioned for correction
- Missing user ID for selection: Validation prevents invalid action
- CICS errors: Captured and displayed with generic "Unable to lookup User" message

## Business Rules
1. User list sorted by user ID (KSDS key field)
2. Page size fixed at 10 users
3. Search starts at specified user ID (GTEQ positioning)
4. Empty search starts from beginning of file
5. Selection codes case-insensitive (U/u, D/d)
6. Only users with admin type can access this program
7. User list includes all user types (Admin, Regular)

## Performance Considerations
- Uses browse (STARTBR/READNEXT/READPREV) rather than multiple READs
- Reads one extra record to detect if next page exists
- ENDBR releases resources after each page load
- Minimal data transfer (only displayed fields)
- No sort or filter operations (relies on KSDS key sequence)
- Maintains positioning via stored first/last user IDs rather than re-browsing from start
