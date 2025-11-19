# Screen Analysis: COADM01

## Overview
**Source File**: `app/bms/COADM01.bms`  
**Map Name**: COADM1A  
**Type**: Menu / Navigation  
**Program**: COADM01C  
**Transaction**: CA00  
**Purpose**: Administrative menu for privileged users

## Purpose

COADM01 provides a centralized menu interface for administrative functions in the CardDemo application. The screen dynamically displays available admin options and allows selection by number. It serves as the hub for user management, database administration, and other admin-only functions.

## Key Fields

### Input Field
- **Option** (`OPTION`): 2 digits, numeric, right-justified with zero-fill
  - Initial cursor position
  - Accepts values 1-6 (or up to CDEMO-ADMIN-OPT-COUNT from copybook)
  - Underlined, turquoise highlight

### Display Fields (Dynamic Menu Options)
The screen supports up to 12 menu options, dynamically populated by COADM01C:

- **OPTN001** through **OPTN012**: 40 characters each, blue, left-aligned
  - Format: "{NUM}. {NAME}"
  - Example: "1. User List (Security)               "
  - Only first N options populated (N = CDEMO-ADMIN-OPT-COUNT)
  - Unused options remain blank

Currently used options (from COADM02Y):
1. User List (Security)
2. User Add (Security)
3. User Update (Security)
4. User Delete (Security)
5. Transaction Type List/Update (Db2)
6. Transaction Type Maintenance (Db2)

### Status Fields
- **Header**: Transaction ID (CA00), program name (COADM01C), date, time
- **Title**: "Admin Menu" (line 4, center-aligned, bright)
- **Prompt**: "Please select an option :" (line 20, bright turquoise)
- **Error/Status Message** (`ERRMSG`): 78 characters, red, bright (line 23)

## Function Keys

- **ENTER**: Execute selected menu option (XCTL to target program)
- **F3**: Exit to sign-on screen (logout)

Note: Other function keys generate "invalid key" error message.

## Screen Layout

```
Row 1-2:  Standard header (transaction, titles, date/time, program)
Row 4:    "Admin Menu" title (centered, bright)
Rows 6-17: Menu options (OPTN001-OPTN012) - dynamically populated
           Currently using rows 6-11 for 6 options
Row 20:   "Please select an option :" prompt with 2-digit entry field
Row 23:   Error/status message line
Row 24:   Function key help: "ENTER=Continue  F3=Exit"
```

## Color Scheme

- **Blue**: Header labels, meta-information, menu option text
- **Yellow**: Title and function key help
- **Turquoise**: Option prompt and input field highlight
- **Red**: Error messages
- **Green**: Success/info messages (controlled by program)

## Navigation Flow

**Entry Points**:
- From COSGN00C after successful admin login
- From COMEN01C (main menu, option 1 for admin users)
- Return from any admin program (COUSR00C, COUSR01C, COUSR02C, COUSR03C, etc.)

**User Workflow**:
1. View available admin options (1-6)
2. Enter option number (e.g., "1" for User List)
3. Press ENTER
4. System XCTLs to selected program
5. Perform admin task
6. F3/F12 in target program returns to admin menu

**Exit Points**:
- F3 → COSGN00C (sign-on screen, logout)
- ENTER with valid option → Selected admin program

## Notable Features

- **Dynamic Configuration**: Menu options populated at runtime from COADM02Y copybook
  - Easy to add/remove options without changing screen map
  - Program-driven menu generation

- **Extensible Design**: Screen supports up to 12 options (OPTN001-OPTN012)
  - Currently using 6 options
  - Room for future expansion without screen redesign

- **Simple Input**: Two-digit numeric entry
  - Right-justified with zero-fill
  - No complex navigation or multiple input fields

- **Central Hub Pattern**: All admin functions funnel through this menu
  - Consistent entry/exit point for admin workflows
  - Preserves navigation context via commarea

- **Graceful Handling of Missing Programs**:
  - Displays "not installed" message for placeholder options
  - No crash if target program doesn't exist (PGMIDERR handled)

- **Minimal Clutter**: Only essential elements visible
  - No visual noise or unnecessary fields
  - Focus on menu selection task

## Menu Option Management

**Data-Driven Menu** (from COADM02Y):
- Option count: CDEMO-ADMIN-OPT-COUNT (currently 6)
- Option structure: Number (2 digits), Name (35 chars), Program (8 chars)
- Program field can be "DUMMY..." for placeholders

**Adding New Options**:
1. Update COADM02Y copybook with new entry
2. Increment CDEMO-ADMIN-OPT-COUNT
3. Recompile COADM01C
4. Screen automatically displays new option

**Current Capacity**: 12 menu slots (6 used, 6 available)

## Comparison to Other Menus

**vs. COMEN01 (Main Menu)**:
- COADM01: Admin-only, fewer options, user management focus
- COMEN01: All users, broader functionality, customer/account/transaction focus

**Common Pattern**:
- Both menus use similar screen layout (title, options, selection prompt)
- Both use COCOM01Y for navigation
- Both support dynamic option configuration
