# Program Analysis: COUSR03C

## Overview
**Source File**: `app/cbl/COUSR03C.cbl`  
**Type**: Online Transaction Processing  
**Transaction ID**: CU03  
**Module**: User Management  
**Business Function**: Delete users from the USRSEC security file

## Business Purpose

COUSR03C allows administrators to remove user accounts from the security system. The program provides a confirmation workflow: first displaying user details for verification, then requiring an explicit F5 keypress to perform the actual deletion. This two-step process helps prevent accidental user deletions. It supports both direct entry (typing a User ID) and pre-selected entry (coming from COUSR00C list screen).

## Key Logic

1. **User Lookup Flow** (Confirmation Phase):
   - ENTER: Fetches user details for the entered User ID
   - Displays first name, last name, and user type (read-only)
   - Password NOT displayed for security
   - Uses READ FOR UPDATE to lock the record
   - Shows message: "Press PF5 key to delete this user ..."

2. **Delete Flow**:
   - F5: Performs the actual deletion after confirmation
   - Issues CICS DELETE on the USRSEC file
   - Clears screen fields after successful deletion
   - Displays success message: "User {ID} has been deleted ..."

3. **Required Field Validation**:
   - User ID: Cannot be empty for lookup or deletion
   - No other validation needed (deletion doesn't modify data)

4. **Navigation Options**:
   - F3: Exit to calling program without deleting
   - F4: Clear screen to start fresh lookup
   - F12: Cancel and return to admin menu

5. **Safety Features**:
   - Two-step process: ENTER (view) → F5 (delete)
   - Record locking prevents concurrent deletion
   - Clear visual feedback before and after deletion

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - Common communication area with program navigation
- `CSUSR01Y` - User security record structure (80-byte USRSEC file layout)
- `COUSR03` - BMS screen map for deletion confirmation form
- `CSMSG01Y` - Standard message definitions
- `CSDAT01Y` - Date/time structures for header
- `COADM02Y` - Admin menu options (for navigation context)

**Files Accessed**:
- `USRSEC` - User security file (READ FOR UPDATE, DELETE)
  - Key: SEC-USR-ID (8 bytes)
  - Operations: READ with UPDATE intent (locks record), DELETE

**Screens**:
- `COUSR03` / `COUSR3A` - User deletion confirmation form

## Program Relationships

**Called By**:
- `COADM01C` - Admin menu (option 4)
- `COUSR00C` - User list (when 'D' action selected on a user)

**Calls**: None (terminal program in user management workflow)

**Navigation**:
- F3/F12 → Returns to calling program (CDEMO-FROM-PROGRAM or COADM01C)
- Uses XCTL to transfer control back

## Notable Patterns

**Two-Phase Deletion**:
- Phase 1 (ENTER): Display user for confirmation
- Phase 2 (F5): Execute actual deletion
- Prevents accidental deletions by requiring explicit F5 confirmation

**Optimistic Locking**:
- READ with UPDATE option locks the record
- DELETE releases the lock and removes record atomically
- Handles NOTFND condition if user deleted between operations

**Simplified Display**:
- Shows only first name, last name, and user type
- Password intentionally NOT displayed (not needed for confirmation)
- All fields display-only (ASKIP attribute in screen)

**Flexible Navigation**:
- Checks CDEMO-FROM-PROGRAM to support multiple entry points
- Defaults to COADM01C (admin menu) if no caller specified
- Maintains bidirectional navigation flow

**State Management**:
- Uses CDEMO-CU03-USR-SELECTED in commarea for pre-population
- Supports both manual entry and pre-selected user scenarios
- CDEMO-PGM-REENTER flag distinguishes first vs. subsequent interactions

**Post-Deletion Cleanup**:
- Calls INITIALIZE-ALL-FIELDS after successful deletion
- Clears screen to prevent confusion about what was just deleted
- Ready for next deletion without residual data

**Error Handling**:
- Field-level validation with cursor positioning
- Color-coded messages (DFHGREEN for success, DFHNEUTR for info, DFHRED implied for errors)
- Graceful handling of NOTFND (user doesn't exist)
- Generic error handling with DISPLAY for unexpected conditions

**Security Concerns**:
- No audit trail of who deleted which user
- No "soft delete" or archival mechanism
- No role-based access control (any admin can delete any user)
- Deleted users are permanently removed

## Business Rules

1. **User ID Required**: Must provide valid User ID for lookup and deletion
2. **Two-Step Confirmation**: ENTER to view, F5 to delete (safety feature)
3. **No Recovery**: Deletion is permanent - no undo or soft delete
4. **Display Before Delete**: Must view user details before deletion allowed
5. **Single User at a Time**: No batch deletion capability

## Performance Considerations

- Single READ and single DELETE per operation
- Record locking duration: from READ to DELETE or session end
- No cascade deletion (doesn't check for related records)
- Screen-driven, one user at a time
- Minimal processing overhead (just lookup and delete)

## Integration Points

**Workflow Integration**:
- Typically used from COUSR00C list screen with pre-selected user
- Can be accessed directly from admin menu for direct ID entry
- Returns to caller after deletion completes

**Data Integrity**:
- No validation of user relationships (accounts, cards, transactions)
- Deleting a user doesn't cascade to other entities
- Could leave orphaned data if user had created records
