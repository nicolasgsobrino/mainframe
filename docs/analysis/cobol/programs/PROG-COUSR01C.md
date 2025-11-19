# Program Analysis: COUSR01C

## Overview
**Source File**: `app/cbl/COUSR01C.cbl`  
**Type**: Online Transaction  
**Module**: User Management  
**Transaction ID**: CU01  
**Screen**: COUSR01

## Business Purpose
Allows administrators to add new users (both regular users and administrators) to the USRSEC security file. Validates all required fields before writing new user record. Prevents duplicate user IDs.

## Key Logic

### Add User Workflow
1. **Initial Display**: Present empty form for user input
2. **Data Entry**: User fills in required fields (first name, last name, user ID, password, user type)
3. **Validation**: Verify all required fields are present and non-blank
4. **Write Record**: Attempt to write new user to USRSEC file
5. **Confirmation**: Display success message or error if duplicate

### Field Validation
Simple required-field validation:
- First Name: Cannot be empty
- Last Name: Cannot be empty
- User ID: Cannot be empty (8 characters)
- Password: Cannot be empty (8 characters, hidden on screen)
- User Type: Cannot be empty (A=Admin, U=User)

### Duplicate Detection
Handles DUPREC/DUPKEY CICS response when user ID already exists in file.

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - Communication area
- `CSUSR01Y` - User security data structure
- `COTTL01Y` - Screen title definitions
- `CSDAT01Y` - Date/time structures
- `CSMSG01Y` - Message definitions

**Files Accessed**:
- `USRSEC` - User security file (KSDS VSAM file, WRITE operation)

**Screens**:
- `COUSR01` - User add screen (BMS map COUSR1A)

## Program Relationships

**Called By**: 
- `COADM01C` - Admin menu

**Calls**: 
- None (terminal program for adding)

**Navigation**:
- PF3 returns to admin menu
- PF4 clears current screen (resets all fields)
- Enter processes add operation

## Notable Patterns

### Minimal Validation
Unlike update programs, only validates required fields are non-empty:
- No format validation (alphanumeric vs alphabetic)
- No length validation beyond field definitions
- No password strength rules
- Relies on screen field definitions for max lengths

### Success Feedback
On successful add:
- Changes error message field to green
- Displays confirmation with new user ID
- Clears all input fields for next entry
- Ready for another user to be added

### Field Initialization
After successful add or PF4 (clear):
- All input fields set to SPACES
- Cursor positioned to first field (FNAME)
- Ready for new entry

### Password Handling
Password field defined as DRK (dark) attribute in screen:
- Characters not displayed as typed
- Stored in clear text in USRSEC file (no encryption)

### Error Recovery
- Duplicate user ID: Cursor positioned to USERID field, message displayed
- Other errors: Generic message, cursor to first field

## Error Handling
- DUPREC/DUPKEY: "User ID already exist" message, cursor to user ID field
- Empty required fields: Specific field-level messages with cursor positioning
- CICS write errors: "Unable to Add User" generic message
- Response codes captured but not displayed to user

## Business Rules
1. User ID must be unique (enforced by KSDS)
2. User ID exactly 8 characters
3. Password exactly 8 characters
4. User type: 'A' = Admin, 'U' = Regular user
5. All fields mandatory (no optional fields)
6. First and last names up to 20 characters
7. No password complexity requirements
8. Passwords stored in clear text (security concern)

## Security Considerations
- Only accessible from admin menu
- No audit trail of who added user
- Password visible to administrator during entry
- Password stored unencrypted in USRSEC file
- No password expiration or change requirements

## Performance Considerations
- Single WRITE operation per user add
- No file browse or search operations
- Minimal validation overhead
- VSAM KSDS enforces unique key constraint
- No batch loading capability
