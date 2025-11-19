# Screen Analysis: COUSR00

## Overview
**Source File**: `app/bms/COUSR00.bms`  
**Type**: List/Browse  
**Program**: COUSR00C  
**Map Name**: COUSR0A  

## Purpose
Displays a paginated list of system users, allowing administrators to search, browse, and select users for update or deletion operations.

## Key Fields

### Header Section
- **TRNNAME**: Transaction ID (CU00)
- **PGMNAME**: Program name (COUSR00C)
- **TITLE01/TITLE02**: Application titles
- **CURDATE/CURTIME**: Current date and time
- **PAGENUM**: Current page number

### Search/Filter Section
- **USRIDIN**: User ID search field (8 characters, optional)
  - Positions browse starting point
  - Empty starts from beginning

### List Grid (10 rows)
Each row displays:
- **SEL0001-SEL0010**: Selection field (1 character input)
  - 'U' or 'u' = Update user
  - 'D' or 'd' = Delete user
- **USRID01-USRID10**: User ID (8 characters, display only)
- **FNAME01-FNAME10**: First name (20 characters, display only)
- **LNAME01-LNAME10**: Last name (20 characters, display only)
- **UTYPE01-UTYPE10**: User type (1 character, display only)
  - 'A' = Admin
  - 'U' = Regular user

### Footer Section
- **ERRMSG**: Error/status message display (78 characters, red text)

## Function Keys

- **ENTER**: Process selection or initiate search
- **F3**: Return to admin menu
- **F7**: Navigate to previous page (backward scroll)
- **F8**: Navigate to next page (forward scroll)

## Navigation Flow

**From**: Admin menu (COADM01C)

**To**:
- Admin menu on PF3
- User update screen (COUSR02C) when 'U' selected
- User delete screen (COUSR03C) when 'D' selected

## Field Attributes

### Input Fields (Turquoise/Green)
- Search user ID: Underlined, green when active
- Selection fields: Underlined, green, accept single character

### Display Fields (Blue)
- User IDs, names, types: Protected, blue text
- Column headers: Neutral color with underlines

### Status/Error (Red/Yellow)
- Error messages: Red, bright
- Function key legend: Yellow

## Screen Layout
```
Row 1:  Header (Tran, Title, Date)
Row 2:  Header (Prog, Title, Time)
Row 4:  Title "List Users" + Page number
Row 6:  Search field
Row 8:  Column headers
Row 9:  Header underlines
Row 10-19: Data rows (10 users)
Row 21: Instructions
Row 23: Error message area
Row 24: Function keys
```

## User Instructions
Displayed on screen:
- "Type 'U' to Update or 'D' to Delete a User from the list"
- Function keys: "ENTER=Continue  F3=Back  F7=Backward  F8=Forward"

## Color Coding
- **Blue**: Static labels, displayed data
- **Turquoise**: Field labels
- **Green**: Input fields
- **Yellow**: Function key legend, titles
- **Red**: Error messages
- **Neutral**: Column headers, instructions

## Data Validation
- Selection field: Only 'U', 'u', 'D', 'd' accepted (validated by program)
- User ID search: 8 characters maximum, alphanumeric
- Must select an existing user row (no blank user ID with selection)

## Pagination Behavior
- Page number displayed in header
- PF7 disabled at first page (shows "already at top" message)
- PF8 disabled at last page (shows "already at bottom" message)
- Search repositions to new starting point and resets to page 1

## Technical Details
- Map set: COUSR00
- Map name: COUSR0A
- Screen size: 24x80
- Mode: INOUT (input and output)
- Storage: AUTO
- Extended attributes: YES (for color support)
