# Screen Analysis: COUSR01

## Overview
**Source File**: `app/bms/COUSR01.bms`  
**Type**: Data Entry  
**Program**: COUSR01C  
**Map Name**: COUSR1A  

## Purpose
Provides a form for administrators to add new users to the system. Captures essential user information including login credentials and user type designation.

## Key Fields

### Header Section
- **TRNNAME**: Transaction ID (CU01)
- **PGMNAME**: Program name (COUSR01C)
- **TITLE01/TITLE02**: Application titles
- **CURDATE/CURTIME**: Current date and time

### User Information Section

**Personal Details**:
- **FNAME**: First name (20 characters, required)
  - Initial cursor position
  - Underlined green input field
- **LNAME**: Last name (20 characters, required)
  - Underlined green input field

**Login Credentials**:
- **USERID**: User ID (8 characters, required)
  - Must be unique in system
  - Underlined green input field
  - Help text: "(8 Char)"
- **PASSWD**: Password (8 characters, required)
  - Dark attribute (characters not visible when typed)
  - Underlined green input field
  - Help text: "(8 Char)"

**Authorization**:
- **USRTYPE**: User type (1 character, required)
  - 'A' = Administrator
  - 'U' = Regular user
  - Underlined green input field
  - Help text: "(A=Admin, U=User)"

### Footer Section
- **ERRMSG**: Error/status message display (78 characters, red text)

## Function Keys

- **ENTER**: Submit new user (add to system)
- **F3**: Return to admin menu
- **F4**: Clear all fields (reset form)
- **F12**: Exit (same as F3)

## Navigation Flow

**From**: Admin menu (COADM01C)

**To**: Admin menu on PF3/F12

## Field Attributes

### Input Fields
All input fields use:
- COLOR=GREEN: Indicates editable fields
- HILIGHT=UNDERLINE: Visual indication of input areas
- UNPROT: Unprotected (allows user input)
- FSET: Field set for modified data tag

### Special Attributes
- **FNAME**: IC (initial cursor) - cursor starts here
- **PASSWD**: DRK (dark) - characters not displayed, FSET for data retrieval

### Labels (Turquoise)
- Field labels in turquoise for easy identification
- Help text in blue for additional guidance

### Error Messages (Red)
- BRT (bright) and FSET attributes
- High visibility for validation errors

## Screen Layout
```
Row 1:  Header (Tran, Title, Date)
Row 2:  Header (Prog, Title, Time)
Row 4:  Title "Add User"
Row 8:  First Name | Last Name
Row 11: User ID | Password
Row 14: User Type
Row 23: Error message area
Row 24: Function keys
```

## User Instructions
Function key legend displayed:
- "ENTER=Add User  F3=Back  F4=Clear  F12=Exit"

## Color Coding
- **Blue**: Static labels, help text
- **Turquoise**: Field labels
- **Green**: Input fields
- **Yellow**: Function key legend, titles
- **Red**: Error messages
- **Neutral**: Screen title

## Data Validation
Performed by COUSR01C program:
- All fields required (no blanks or low-values)
- User ID must be unique (VSAM enforced)
- User type must be 'A' or 'U'
- Field lengths enforced by screen definitions

## Success Behavior
On successful user add:
- Success message displayed in green
- Shows added user ID in confirmation
- All fields cleared automatically
- Ready for next user entry
- Cursor returns to first name field

## Error Handling
Specific error messages displayed for:
- "First Name can NOT be empty..."
- "Last Name can NOT be empty..."
- "User ID can NOT be empty..."
- "Password can NOT be empty..."
- "User Type can NOT be empty..."
- "User ID already exist..." (duplicate)
- "Unable to Add User..." (system error)

Cursor automatically positioned to field in error.

## Technical Details
- Map set: COUSR01
- Map name: COUSR1A
- Screen size: 24x80
- Mode: INOUT (input and output)
- Storage: AUTO
- Extended attributes: YES (for color support)
- Control: ALARM, FREEKB (keyboard unlocked, alarm on errors)

## Security Notes
- Password entry hidden (dark attribute)
- No password strength indicator
- No confirmation field for password
- Administrator can see entered password in memory
- No audit of who added the user
