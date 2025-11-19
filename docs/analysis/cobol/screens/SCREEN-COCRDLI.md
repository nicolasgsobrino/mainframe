# Screen Analysis: COCRDLI

## Overview
**Source File**: `app/bms/COCRDLI.bms`
**Type**: Data Entry and Inquiry List
**Program**: COCRDLIC (Card List Inquiry)
**Map Name**: CCRDLIA

## Purpose
Displays a paginated list of credit cards with filtering capabilities by account number or card number. Users can select individual cards to view details or update information. This is the primary card browsing interface for the CardDemo application.

## Screen Layout (24x80)

### Header Section (Lines 1-2)
- Transaction name (TRNNAME)
- Screen title (TITLE01/TITLE02) 
- Current date (mm/dd/yy format)
- Current time (hh:mm:ss format)
- Program name (PGMNAME)

### Filter Section (Lines 6-7)
**Input Fields**:
- `ACCTSID` (11 chars) - Account Number filter (line 6, col 44)
  - Initial cursor position (IC attribute)
  - Underlined, green color
  - Optional filter field
  
- `CARDSID` (16 chars) - Credit Card Number filter (line 7, col 44)
  - Underlined, green color
  - Optional filter field

Users can filter by either account number, card number, or leave both blank to see all cards.

### List Header (Lines 9-10)
Column headers with underline separators:
- **Select** (col 10) - Selection action code
- **Account Number** (col 21-34) - 11-digit account ID
- **Card Number** (col 45-57) - 16-digit card number
- **Active** (col 66-72) - Card active status (Y/N)

### Data Rows (Lines 11-17) - 7 Records Per Page
Each row contains:
- `CRDSELn` (1 char) - Selection field (S=View, U=Update)
  - Protected but user can overtype
  - Underlined for visibility
  
- `ACCTNOn` (11 chars) - Account number display
  - Protected, read-only
  
- `CRDNUMn` (16 chars) - Card number display
  - Protected, read-only
  
- `CRDSTSn` (1 char) - Active status (Y/N)
  - Protected, read-only

- `CRDSTPn` (1 char, hidden) - Stop field for row processing
  - Dark attribute (not visible to user)
  - Used internally for field control

### Message Areas (Lines 20, 23)
- `INFOMSG` (45 chars, line 20) - Informational messages
- `ERRMSG` (78 chars, line 23) - Error messages in red, bright

### Navigation Footer (Line 24)
Function key help:
- **F3** - Exit to previous screen
- **F7** - Backward (previous page)
- **F8** - Forward (next page)

### Page Indicator (Line 4)
- "Page" label with page number (PAGENO, 3 chars)

## Function Keys
- **F3**: Exit - Return to calling program/menu
- **F7**: Backward - Display previous page of cards
- **F8**: Forward - Display next page of cards
- **Enter**: Process selection - Execute S (view) or U (update) action

## Selection Codes
- **S** - View card details (transfers to COCRDSLC program)
- **U** - Update card information (transfers to COCRDUPC program)
- **Blank** - No action for this row

## Navigation Flow
**Entry Points**:
- From main menu (COMEN01C)
- From account inquiry/update screens
- Direct transaction invocation

**Exit Points**:
- F3 → Return to calling program
- Selection S → COCRDSLC (Card Detail View)
- Selection U → COCRDUPC (Card Update)

## Technical Characteristics

### Display Attributes
- Color coding: Blue (labels), Yellow (titles), Green (input), Red (errors), Turquoise (prompts)
- Highlighting: Underline for input fields
- Cursor positioning: Initial cursor (IC) on ACCTSID field

### Field Protection
- Filter fields: Unprot (user can modify)
- List data fields: Prot (display only)
- Selection fields: Prot with FSET (program sets, user can overtype)

### Screen Control
- FREEKB: Keyboard unlocked after display
- Storage=AUTO: BMS manages storage
- Mode=INOUT: Supports input and output operations

## Data Flow
1. User enters filter criteria (optional: account number and/or card number)
2. Program queries CARDDAT file based on filters
3. Screen displays up to 7 matching cards
4. User enters selection code (S or U) next to desired card
5. Program validates selection and transfers to appropriate screen

## Modernization Considerations

### Modern UI Equivalent
- Web: Paginated data table with search filters and action buttons
- Desktop: DataGrid with filter textboxes and context menu actions
- Mobile: Scrollable card list with swipe actions

### UI/UX Improvements
- Replace function keys with button controls (Previous, Next, Exit, View, Edit)
- Replace single-character selection codes with icon buttons or row actions
- Increase page size (7 records is very small - consider 20-50 for web)
- Add sortable column headers
- Implement type-ahead or auto-complete for account/card filters
- Show record count and page indicator (e.g., "Page 2 of 15, showing 10 of 142 records")
- Add multi-select capability with bulk actions

### Responsive Design
- Collapse to card-based layout on mobile devices
- Sticky header row during scrolling
- Inline search with live filtering
- Infinite scroll or "Load More" button as alternative to pagination

### Accessibility
- Proper ARIA labels for screen readers
- Keyboard navigation support (Tab, Arrow keys)
- High contrast mode support
- Focus indicators for interactive elements
