# Copybook Analysis: CSUSR01Y

## Overview
**Source File**: `app/cpy/CSUSR01Y.cpy`  
**Type**: Data Structure - User Security Record  
**Used By**: COUSR00C, COUSR01C, COUSR02C, COUSR03C (user management programs)

## Purpose
Defines the record layout for the USRSEC file, which stores user authentication and authorization information. This is the security master file for the CardDemo application.

## Structure Overview
Single flat record structure (80 bytes) containing user identification, personal information, credentials, and authorization level.

## Key Fields

### User Identification (8 bytes)
- **SEC-USR-ID** (X(08)): Unique user identifier
  - Primary key for USRSEC KSDS file
  - Used for login authentication
  - Alphanumeric, 8 characters

### Personal Information (40 bytes)
- **SEC-USR-FNAME** (X(20)): User's first name
  - Displayed in user lists and greetings
  - Alphabetic, 20 characters
  
- **SEC-USR-LNAME** (X(20)): User's last name
  - Displayed in user lists and greetings
  - Alphabetic, 20 characters

### Security Credentials (8 bytes)
- **SEC-USR-PWD** (X(08)): User password
  - Used for authentication at login
  - Stored in clear text (unencrypted)
  - 8 characters
  - **Security concern**: No encryption or hashing

### Authorization (1 byte)
- **SEC-USR-TYPE** (X(01)): User type/role
  - 'A' = Administrator (full access)
  - 'U' = Regular user (limited access)
  - Controls program access permissions

### Unused Space (23 bytes)
- **SEC-USR-FILLER** (X(23)): Reserved for future use
  - Pads record to standard length
  - Available for additional user attributes

## Notable Patterns

### Fixed-Length Record
All fields fixed length (80 bytes total):
- Simplifies file I/O operations
- Predictable storage requirements
- No variable-length complexity

### Flat Structure
No hierarchical groups or redefines:
- Simple field access
- Easy to understand and maintain
- No complex data relationships

### Clear Text Storage
Password stored without encryption:
- **Major security vulnerability**
- Accessible to anyone with file access
- Modern replacement should use hashing (bcrypt, PBAC2, etc.)

### Role-Based Access
Single character user type:
- Simple boolean-like authorization
- Could be extended to more granular roles
- Currently only two levels (admin vs user)

## Usage Context

### File Operations
Used with USRSEC VSAM KSDS file:
- Key field: SEC-USR-ID (8 bytes)
- Record length: 80 bytes
- Access: Direct (READ, WRITE, UPDATE, DELETE) and browse (STARTBR/READNEXT)

### Programs
- **COUSR00C**: Browse/list users, reads records sequentially
- **COUSR01C**: Add new users, writes new records
- **COUSR02C**: Update existing users, reads and updates records
- **COUSR03C**: Delete users, deletes records
- **COSGN00C**: Authentication, reads for login validation

### Authentication Flow
1. User enters SEC-USR-ID and SEC-USR-PWD at login
2. Program reads USRSEC file by SEC-USR-ID
3. Compares entered password with SEC-USR-PWD
4. If match, user authenticated with SEC-USR-TYPE role

## Security Considerations

### Current Weaknesses
1. **No password encryption**: Passwords stored in clear text
2. **No password expiration**: Users never required to change passwords
3. **No password history**: Can reuse old passwords
4. **No account lockout**: Unlimited login attempts possible
5. **No audit trail**: No record of password changes or login attempts
6. **Limited roles**: Only two authorization levels

### Modernization Recommendations
1. Add password hash field (e.g., SHA-256 with salt)
2. Add password change date
3. Add last login timestamp
4. Add failed login counter
5. Add account status (active/locked/expired)
6. Expand user type to support more granular roles
7. Add created date and last modified date
8. Add audit fields (created by, modified by)

## Data Dictionary

| Field | Type | Length | Description | Business Rule |
|-------|------|--------|-------------|---------------|
| SEC-USR-ID | X | 8 | User ID | Unique, required, key field |
| SEC-USR-FNAME | X | 20 | First name | Required, alphabetic |
| SEC-USR-LNAME | X | 20 | Last name | Required, alphabetic |
| SEC-USR-PWD | X | 8 | Password | Required, clear text |
| SEC-USR-TYPE | X | 1 | User type | Required, 'A' or 'U' |
| SEC-USR-FILLER | X | 23 | Reserved | Unused |

## File Characteristics
- **File**: USRSEC
- **Organization**: KSDS (Key Sequenced Data Set)
- **Record Length**: 80 bytes
- **Key Field**: SEC-USR-ID (offset 0, length 8)
- **Key Type**: Unique
- **Access**: Random and sequential
