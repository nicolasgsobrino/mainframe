# Program Analysis: CBSTM03B

## Overview
**Source File**: `app/cbl/CBSTM03B.CBL`  
**Type**: Batch Subroutine  
**Module**: Statement Generation

## Business Purpose
File I/O utility subroutine called by CBSTM03A to handle all file operations (open, read, close) for the statement generation process. Centralizes file handling logic and provides consistent error reporting back to the calling program.

## Key Logic

### Subroutine Interface
- **Called With**: LK-M03B-AREA parameter block containing:
  - DD name (TRNXFILE, XREFFILE, CUSTFILE, ACCTFILE)
  - Operation code (O=Open, C=Close, R=Read sequential, K=Read random)
  - Return code (file status returned here)
  - Key field (for random reads)
  - Key length (for random reads)
  - Data buffer (1000 bytes for record data)

### File Processing Operations
1. **Transaction File (TRNXFILE)**: Indexed, sequential access
2. **Cross-Reference File (XREFFILE)**: Indexed, sequential access
3. **Customer File (CUSTFILE)**: Indexed, random access by customer ID
4. **Account File (ACCTFILE)**: Indexed, random access by account ID

### Operation Handling
- Evaluates DD name to route to appropriate file paragraph
- Processes operation code (open/read/close) for each file
- Returns file status code to caller for error handling
- Uses GO TO for exit after each operation (mainframe pattern)

## Data Dependencies

**Key Copybooks**: None (uses standard COBOL file I/O)

**Files Accessed**:
- `TRNX-FILE` - Transaction data (indexed, sequential)
- `XREF-FILE` - Card/account cross-reference (indexed, sequential)
- `CUST-FILE` - Customer master (indexed, random)
- `ACCT-FILE` - Account master (indexed, random)

**Record Layouts**:
- Transaction: 16-char card + 16-char ID + 318 bytes data
- Cross-reference: 16-char card + 34 bytes data
- Customer: 9-char ID + 491 bytes data
- Account: 11-digit ID + 289 bytes data

## Program Relationships
**Calls**: None  
**Called By**: `CBSTM03A` (main statement generation program)

## Notable Patterns

### Subroutine Design
- Generic parameter-driven interface
- Single entry point with operation routing
- Consistent return code handling
- Reusable across multiple calling programs

### File Access Patterns
- **Sequential Files**: Read-only, sequential processing
- **Random Files**: Key-based direct access with customer/account IDs
- **File Status**: Two-byte status code returned for every operation
- **Key Handling**: Dynamic key length and substring reference

### Legacy Techniques
- GO TO statements for paragraph exit points
- USING parameter for linkage section
- File status split into STAT1 and STAT2 components
- GOBACK instead of STOP RUN for subroutine return

## Business Rules
1. All file I/O centralized in this subroutine
2. Caller provides DD name and operation code
3. File status returned for every operation
4. Random reads require key and key length
5. Sequential reads use current file position
6. Files must be opened before read operations
