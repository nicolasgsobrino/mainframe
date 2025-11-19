# Screen Analysis: COUSR03

## Overview
**Source File**: `app/bms/COUSR03.bms`  
**Map Name**: COUSR3A  
**Type**: Confirmation / Deletion Form  
**Program**: COUSR03C  
**Transaction**: CU03  
**Purpose**: Delete users from security system with confirmation

## Purpose

COUSR03 provides a confirmation interface for user deletion. The screen first displays user details as read-only information to verify the correct user is selected, then requires an explicit F5 keypress to complete the deletion. This two-step workflow prevents accidental user deletions.

## Key Fields

### Input Field
- **User ID** (`USRIDIN`): 8 characters, initial cursor position, editable, underlined, green
  - Used for lookup only - cannot be changed once fetched
  - Entry point for deletion workflow

### Display-Only Fields (Read-Only)
All fields below are ASKIP (auto-skip, protected), displayed in blue with underline:

- **First Name** (`FNAME`): 20 characters, blue, display-only
  - Shows current user's first name for confirmation
  
- **Last Name** (`LNAME`): 20 characters, blue, display-only
  - Shows current user's last name for confirmation
  
- **User Type** (`USRTYPE`): 1 character, blue, display-only
  - Shows 'A' (Admin) or 'U' (User)
  - Help text: "(A=Admin, U=User)"
  - Note: Password field not included (unnecessary for deletion confirmation)

### Status Fields
- **Header**: Transaction ID (CU03), program name (COUSR03C), date, time
- **Title**: "Delete User" (line 4, center-aligned, bright)
- **Separator Line**: Yellow asterisks (70 chars) separating lookup from confirmation area
- **Error/Status Message** (`ERRMSG`): 78 characters, red, bright (line 23)

## Function Keys

- **ENTER**: Fetch and display user details for confirmation
- **F3**: Cancel and exit to previous screen (no deletion)
- **F4**: Clear screen to start fresh deletion
- **F5**: Execute deletion after confirmation
- **F12**: Cancel and exit to admin menu (no deletion - note: not listed on screen but available)

## Screen Layout

```
Row 1-2: Standard header (transaction, titles, date/time, program)
Row 4:   "Delete User" title (centered, bright)
Row 6:   User ID entry field
Row 8:   Yellow separator line (70 asterisks)
Row 11:  First Name (display-only, blue)
Row 13:  Last Name (display-only, blue)
Row 15:  User Type (display-only, blue) with "(A=Admin, U=User)" hint
Row 23:  Error/status message line
Row 24:  Function key help: "ENTER=Fetch  F3=Back  F4=Clear  F5=Delete"
```

## Color Scheme

- **Blue**: Header labels, meta-information, and read-only confirmation fields
- **Yellow**: Title and separator line
- **Green**: User ID input field (editable)
- **Turquoise**: Field labels in confirmation area
- **Red**: Error messages
- **Green**: Success messages (controlled by program)

## Navigation Flow

**Entry Points**:
- From COADM01C (Admin menu, option 4) - blank User ID
- From COUSR00C (User list) - User ID pre-populated from selection with 'D' action

**User Workflow**:
1. Enter User ID → ENTER (fetch and display user details)
2. Verify user information displayed (first name, last name, user type)
3. Read confirmation message: "Press PF5 key to delete this user ..."
4. F5 to confirm deletion
5. Success message displays: "User {ID} has been deleted ..."
6. Screen clears, ready for next deletion

**Exit Points**:
- F3 → Previous screen (Admin menu or User list) without deleting
- F12 → Admin menu (COADM01C) without deleting

## Notable Features

- **Two-Phase Workflow**: 
  - Phase 1 (ENTER): Display user for verification
  - Phase 2 (F5): Execute deletion with explicit confirmation

- **Read-Only Display**: All user fields except User ID are protected (ASKIP)
  - Prevents accidental modification during deletion
  - Blue color indicates non-editable status

- **Password Omitted**: Password field not shown on deletion screen
  - Unnecessary for deletion confirmation
  - Improves security by not displaying sensitive data

- **Visual Separation**: Yellow asterisk line separates lookup area from confirmation area

- **Clear Status Messages**:
  - Info: "Press PF5 key to delete this user ..." (neutral color)
  - Success: "User {ID} has been deleted ..." (green)
  - Error: "User ID NOT found..." (red)

- **Post-Deletion Cleanup**: Screen clears after successful deletion to avoid confusion

- **Safety-Focused Design**:
  - Explicit confirmation required (F5)
  - Cancel options at multiple points (F3, F12, or simply not pressing F5)
  - Visual feedback showing exactly what will be deleted

## Comparison to Other User Screens

**vs. COUSR00 (List)**: Simple confirmation form vs. paginated grid
**vs. COUSR01 (Add)**: Display-only vs. all-editable form
**vs. COUSR02 (Update)**: Display-only vs. editable form with save options
**Key Difference**: Only screen in user management suite with all fields protected (read-only)
