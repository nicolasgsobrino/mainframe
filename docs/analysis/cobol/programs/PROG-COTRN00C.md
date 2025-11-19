# Program Analysis: COTRN00C

## Overview
**Source File**: `app/cbl/COTRN00C.cbl`  
**Type**: Online/CICS  
**Module**: Transaction Management  
**Transaction ID**: CT00

## Business Purpose
Provides paginated transaction list viewing functionality. Allows users to search for transactions by ID and browse through transaction records with forward/backward pagination. Users can select a transaction (by typing 'S') to view its details in COTRN01C.

## Key Logic

### Pagination
- Displays 10 transactions per page
- Supports forward (PF8) and backward (PF7) navigation
- Uses STARTBR/READNEXT/READPREV for VSAM browsing
- Tracks first and last transaction IDs on current page for navigation continuity
- Indicates when more pages are available

### Search
- Optional search by Transaction ID (numeric)
- Searches from specified ID forward
- If no ID specified, starts from beginning of file

### Transaction Selection
- User types 'S' in selection field next to any transaction
- XCTLs to COTRN01C (transaction detail) with selected transaction ID
- Passes transaction context through COMMAREA

### Data Retrieval
- Reads from TRANSACT file (VSAM KSDS)
- Browses using transaction ID as key
- Displays: Transaction ID, Date, Description, Amount
- Formats timestamp to MM/DD/YY display format
- Formats amount with sign and decimal places

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - Common COMMAREA (navigation & context)
- `CVTRA05Y` - Transaction record layout (TRAN-RECORD)
- `COTRN00` - Screen map (transaction list display)
- `CSMSG01Y` - Message definitions
- `CSDAT01Y` - Date/time structures (for timestamp formatting)
- `COTTL01Y` - Screen title definitions

**Files Accessed**:
- `TRANSACT` - Transaction file (read/browse only)

**Screens**:
- `COTRN0A` (from COTRN00.bms) - Transaction list display

## Program Relationships

**Calls**: 
- COTRN01C - Transaction detail view (XCTL when user selects transaction)

**Called By**: 
- COMEN01C - Main menu (via menu option)
- COTRN01C - Transaction detail (return via PF3)

**Navigation**:
- F3: Return to main menu (COMEN01C)
- F7: Page backward
- F8: Page forward
- Enter: Process search/selection
- PF keys validated; invalid keys show error message

## Screen Layout
The transaction list screen (COTRN0A) displays:
- Header with transaction ID, program name, date, time
- Search field for Transaction ID
- 10-row grid showing:
  - Selection field (1 char)
  - Transaction ID (16 chars)
  - Date (8 chars, MM/DD/YY)
  - Description (26 chars)
  - Amount (12 chars, formatted with sign)
- Page number indicator
- Instructions: "Type 'S' to View Transaction details"
- Function key help line

## Notable Patterns

### Browse Management
- Properly opens (STARTBR), reads (READNEXT/READPREV), and closes (ENDBR) browse
- Handles EOF gracefully with user-friendly messages
- Maintains browse position for pagination

### Error Handling
- Validates numeric transaction ID input
- Provides specific messages for different error conditions
- Uses WS-ERR-FLG to control error flow
- Sets cursor position to error field (-1 to length field)

### Pagination Logic
- Tracks page number in COMMAREA (CDEMO-CT00-PAGE-NUM)
- Stores first/last IDs on page for navigation anchor points
- Indicates next page availability (NEXT-PAGE-FLG)
- Handles edge cases (top/bottom of file)

### COMMAREA Usage
- Reuses CDEMO-CT00-INFO structure for transaction-specific context:
  - First/last transaction IDs on current page
  - Page number
  - Next page availability flag
  - Selected transaction ID and selection flag
- Maintains program context through pseudo-conversational cycles

### Screen Data Handling
- Uses EVALUATE to populate 10 screen rows dynamically
- Separate initialize routine to clear unpopulated rows
- Conditional ERASE on SEND based on SEND-ERASE-FLG
