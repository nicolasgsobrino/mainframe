# Screen Analysis: COUSR02

## Overview
**Source File**: `app/bms/COUSR02.bms`  
**Map Name**: COUSR2A  
**Type**: Data Entry / Update Form  
**Program**: COUSR02C  
**Transaction**: CU02  
**Purpose**: Update existing user details in security system

## Purpose

COUSR02 provides a form-based interface for administrators to modify user records. The screen displays current user information (first name, last name, password, user type) and allows editing of all fields except the User ID, which serves as the immutable record key.

## Key Fields

### Input Fields
- **User ID** (`USRIDIN`): 8 characters, initial cursor position
  - Used for lookup - cannot be changed once fetched
  
- **First Name** (`FNAME`): 20 characters, editable, underlined, green
  - Current value populated after user lookup
  
- **Last Name** (`LNAME`): 20 characters, editable, underlined, green
  - Current value populated after user lookup
  
- **Password** (`PASSWD`): 8 characters, dark/hidden entry, underlined
  - Hidden input (DRK attribute) for privacy
  - Help text: "(8 Char)"
  
- **User Type** (`USRTYPE`): 1 character, editable, underlined, green
  - Values: 'A' (Admin) or 'U' (User)
  - Help text: "(A=Admin, U=User)"

### Display Fields
- **Header**: Transaction ID (CU02), program name (COUSR02C), date, time
- **Title**: "Update User" (line 4, center-aligned, bright)
- **Separator Line**: Yellow asterisks (70 chars) separating lookup from edit area
- **Error/Status Message** (`ERRMSG`): 78 characters, red, bright (line 23)

## Function Keys

- **ENTER**: Fetch user details for the entered User ID
- **F3**: Save changes and exit to previous screen
- **F4**: Clear all fields to start fresh update
- **F5**: Save changes without exiting (stays on update screen)
- **F12**: Cancel and exit to admin menu (no save)

## Screen Layout

```
Row 1-2: Standard header (transaction, titles, date/time, program)
Row 4:   "Update User" title (centered)
Row 6:   User ID entry field
Row 8:   Yellow separator line (70 asterisks)
Row 11:  First Name (left), Last Name (right) - same line
Row 13:  Password with "(8 Char)" hint
Row 15:  User Type with "(A=Admin, U=User)" hint
Row 23:  Error/status message line
Row 24:  Function key help: "ENTER=Fetch  F3=Save&Exit  F4=Clear  F5=Save  F12=Cancel"
```

## Color Scheme

- **Blue**: Header labels and meta-information
- **Yellow**: Titles and separator line
- **Green**: Editable input fields
- **Turquoise**: Field labels in edit area
- **Red**: Error messages
- **Neutral/Green**: Success/info messages (controlled by program)

## Navigation Flow

**Entry Points**:
- From COADM01C (Admin menu, option 3) - blank User ID
- From COUSR00C (User list) - User ID pre-populated from selection

**User Workflow**:
1. Enter User ID → ENTER (fetch current details)
2. Modify desired fields (first name, last name, password, user type)
3. F5 to save (or F3 to save and exit)
4. Success message displays: "User {ID} has been updated ..."

**Exit Points**:
- F3 → Previous screen (Admin menu or User list)
- F12 → Admin menu (COADM01C)

## Notable Features

- **Two-Phase Interaction**: 
  - Phase 1: Lookup user by ID
  - Phase 2: Edit and save changes

- **Hidden Password Entry**: Password field uses DRK attribute to prevent shoulder surfing

- **Inline Help**: Field hints show format requirements (8 Char, A=Admin/U=User)

- **Visual Separation**: Yellow asterisk line separates lookup area from edit area

- **Flexible Save Options**: 
  - F5: Save and continue (for multiple edits)
  - F3: Save and exit (when done)

- **Change Detection**: Program validates that at least one field changed before saving
