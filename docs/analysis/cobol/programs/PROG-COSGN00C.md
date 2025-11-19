# Program Analysis: COSGN00C

## Overview
**Source File**: `app/cbl/COSGN00C.cbl`
**Type**: Online Transaction Program (CICS)
**Module**: Authentication
**Transaction ID**: CC00

## Business Purpose
COSGN00C is the authentication entry point for the CardDemo application. It presents a sign-on screen to users, validates their credentials against the user security file (USRSEC), and routes authenticated users to the appropriate menu based on their role (Admin vs. Regular User). This is the gateway that all users must pass through to access the system.

## Key Logic

### Initial Entry (EIBCALEN = 0)
When first invoked (no COMMAREA):
1. Initialize screen with LOW-VALUES
2. Set cursor to User ID field
3. Display sign-on screen

### Enter Key Processing
When user presses ENTER:
1. Receive map data (User ID and Password)
2. Validate both fields are not empty
3. Convert both to uppercase for case-insensitive comparison
4. Read USRSEC file using User ID as key
5. Compare stored password with entered password
6. If valid:
   - Initialize COMMAREA with user ID and type
   - Route to COADM01C (admin menu) if user type = 'A'
   - Route to COMEN01C (regular menu) if user type = 'U'
7. If invalid:
   - Display error message and re-prompt

### F3 Key Processing
Displays "Thank you" message and ends session.

### Error Handling
- Missing User ID → "Please enter User ID ..."
- Missing Password → "Please enter Password ..."
- User not found → "User not found. Try again ..." (RESP 13)
- Wrong password → "Wrong Password. Try again ..."
- File read error → "Unable to verify the User ..."

## Data Dependencies

**Key Copybooks**:
- `COCOM01Y` - COMMAREA structure (initializes session context)
- `COSGN00` - BMS screen map (sign-on screen layout)
- `CSUSR01Y` - User security data structure (SEC-USER-DATA)
- `CSDAT01Y` - Date/time structures (for header display)
- `CSMSG01Y` - Common messages
- `COTTL01Y` - Title definitions

**Files Accessed**:
- `USRSEC` - User security file (VSAM KSDS keyed by User ID)
  - READ operation to validate credentials

**Screens** (BMS):
- `COSGN0A` (mapset COSGN00) - Sign-on screen

## Program Relationships

**Called By**: CICS region (initial transaction CC00)

**Calls (XCTL)**:
- `COADM01C` - Admin menu (if user type = 'A')
- `COMEN01C` - Regular user menu (if user type = 'U')

**Navigation**:
- Entry point: Direct transaction invocation (no callers)
- Exit points: XCTL to menu programs or RETURN

## Notable Patterns

### Pseudo-Conversational Design
Standard CICS pattern:
- RETURN with TRANSID to remain pseudo-conversational
- Passes COMMAREA between interactions
- No waiting on terminal I/O (efficient resource usage)

### Cursor Positioning
Sets cursor to specific field (`MOVE -1 TO field`) on validation errors, improving user experience.

### Password Security
- Password field has DRK (dark) attribute in BMS to hide input
- Password stored and compared as uppercase (simple, not modern best practice)
- No password encryption or hashing (legacy security model)

### Role-Based Routing
Routes users to different starting points based on user type:
- Admin users → COADM01C (admin functions)
- Regular users → COMEN01C (standard menu)

### COMMAREA Initialization
Initializes key COMMAREA fields on successful authentication:
- `CDEMO-FROM-TRANID/PROGRAM` - Where user came from (for navigation)
- `CDEMO-USER-ID` - Authenticated user ID (session identity)
- `CDEMO-USER-TYPE` - User role (for authorization)
- `CDEMO-PGM-CONTEXT` - Set to 0 (fresh entry)

### Function Key Handling
Uses standard DFHAID copybook for AID key detection (DFHENTER, DFHPF3).

## Migration Considerations

**Modern authentication equivalent**:
- Replace with ASP.NET Core Identity or OAuth2/OIDC
- Implement secure password hashing (bcrypt, PBKDF2)
- Add MFA support
- Session management via JWT tokens or cookie authentication
- Replace USRSEC file with SQL database (Users table)

**Security enhancements needed**:
- Hash passwords instead of plaintext comparison
- Add account lockout after failed attempts
- Implement password complexity requirements
- Add audit logging for authentication attempts
- HTTPS/TLS for credential transmission

**User experience**:
- Modern web UI instead of 3270 screen
- "Forgot password" functionality
- "Remember me" option
- Single sign-on (SSO) integration
