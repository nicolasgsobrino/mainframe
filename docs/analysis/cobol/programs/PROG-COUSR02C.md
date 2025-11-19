# Program Analysis: COUSR02C

## Overview
**Source File**: `app/cbl/COUSR02C.cbl`  
**Type**: Online Transaction Processing  
**Transaction ID**: CU02  
**Module**: User Management  
**Business Function**: Update existing users in the USRSEC security file

## Business Purpose

COUSR02C enables administrators to modify existing user records in the security system. Users can update first name, last name, password, and user type (Admin/Regular) for any registered user. The program supports both direct entry (typing a User ID) and pre-selected entry (coming from COUSR00C list screen with a user already selected). It uses optimistic locking (READ FOR UPDATE) to prevent concurrent modification conflicts.

## Key Logic

1. **User Lookup Flow**:
   - ENTER: Fetches user details for the entered User ID
   - Displays current values in editable form
   - Uses READ FOR UPDATE to lock the record

2. **Update Flow**:
   - F5: Saves modifications only if at least one field changed
   - Compares each field (first name, last name, password, user type) to detect changes
   - Sets USR-MODIFIED flag when any difference detected
   - Performs REWRITE to update the file
   - Displays success message with user ID

3. **Required Field Validation**:
   - User ID: Cannot be empty
   - First Name: Cannot be empty
   - Last Name: Cannot be empty
   - Password: Cannot be empty
   - User Type: Cannot be empty (must be 'A' or 'U')

4. **Additional Features**:
   - F3: Save changes and return to calling program (default COADM01C)
   - F4: Clear screen to start fresh update
   - F12: Cancel and return to admin menu without saving

5. **Change Detection Logic**:
   - Tracks if any field has been modified before allowing update
   - Prevents no-op updates with message "Please modify to update ..."
   - Only issues REWRITE when USR-MODIFIED-YES flag is set

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - Common communication area with program navigation
- `CSUSR01Y` - User security record structure (80-byte USRSEC file layout)
- `COUSR02` - BMS screen map for update form
- `CSMSG01Y` - Standard message definitions
- `CSDAT01Y` - Date/time structures for header
- `COADM02Y` - Admin menu options (for navigation context)

**Files Accessed**:
- `USRSEC` - User security file (READ FOR UPDATE, REWRITE)
  - Key: SEC-USR-ID (8 bytes)
  - Operations: READ with UPDATE intent, REWRITE

**Screens**:
- `COUSR02` / `COUSR2A` - User update form

## Program Relationships

**Called By**:
- `COADM01C` - Admin menu (option 3)
- `COUSR00C` - User list (when 'U' action selected on a user)

**Calls**: None (terminal program in user management workflow)

**Navigation**:
- F3/F12 → Returns to calling program (CDEMO-FROM-PROGRAM or COADM01C)
- Uses XCTL to transfer control back

## Notable Patterns

**Optimistic Locking**:
- READ with UPDATE option locks the record
- REWRITE releases the lock and updates atomically
- Handles NOTFND condition if user deleted between operations

**Change Detection**:
- Compares each field individually to detect modifications
- Uses condition name USR-MODIFIED-YES/NO to track changes
- Prevents unnecessary REWRITE operations

**Flexible Navigation**:
- Checks CDEMO-FROM-PROGRAM to support multiple entry points
- Defaults to COADM01C (admin menu) if no caller specified
- Maintains bidirectional navigation flow

**State Management**:
- Uses CDEMO-CU02-USR-SELECTED in commarea for pre-population
- Supports both manual entry and pre-selected user scenarios
- CDEMO-PGM-REENTER flag distinguishes first vs. subsequent interactions

**Error Handling**:
- Field-level validation with cursor positioning
- Color-coded messages (DFHRED for errors, DFHGREEN for success, DFHNEUTR for info)
- Graceful handling of NOTFND (user doesn't exist)
- Generic error handling with DISPLAY for unexpected conditions

**Security Concerns**:
- Password displayed on screen (DRK attribute hides it, but still visible in copybooks)
- Password stored in clear text in USRSEC file
- No password format validation
- No audit trail of who updated what

## Business Rules

1. **All Fields Required**: Cannot save update with any blank field
2. **Change Required to Update**: Must modify at least one field before F5/F3 saves
3. **User ID Immutable**: User ID cannot be changed (read-only after lookup)
4. **User Type Values**: Must be 'A' (Admin) or 'U' (User)
5. **No Format Validation**: Names and passwords accept any characters

## Performance Considerations

- Single READ and single REWRITE per update operation
- Record locking duration: from READ to REWRITE or session end
- No batch processing or mass updates supported
- Screen-driven, one user at a time
