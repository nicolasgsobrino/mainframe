# Program Analysis: CBSTM03A

## Overview
**Source File**: `app/cbl/CBSTM03A.CBL`  
**Type**: Batch  
**Module**: Statement Generation

## Business Purpose
Generates monthly account statements in two formats (plain text and HTML) by reading transaction data and combining it with customer and account information. This program produces customer-facing statements showing account details, current balance, FICO score, and transaction summaries for the reporting period.

## Key Logic

### Statement Generation Process
1. **Control Block Inspection**: Uses mainframe control blocks (PSA, TCB, TIOT) to display job and dataset information
2. **File Processing Sequence**:
   - Opens transaction file (TRNXFILE) and loads all transactions into memory array
   - Reads cross-reference file (XREFFILE) sequentially to get card-to-account mappings
   - For each card, retrieves customer and account data
   - Generates statement in both text and HTML formats
3. **Memory Management**: Uses 2-dimensional array (51 cards × 10 transactions) to store transaction data in memory
4. **Output Generation**: Creates dual-format statements with header, customer address, account basics, and transaction details

### Statement Components
- **Header**: Bank information and account number
- **Customer Information**: Name and address (from customer file)
- **Basic Details**: Account ID, current balance, FICO score
- **Transaction Summary**: List of transactions with amounts, total
- **HTML Version**: Styled HTML table with color-coded sections

### Processing Features
- Uses ALTER and GO TO statements (legacy mainframe pattern)
- Calls CBSTM03B subroutine for all file I/O operations
- Handles multiple cards per customer via 2D array structure
- Calculates running totals of transaction amounts

## Data Dependencies

**Key Copybooks**:
- `COSTM01` - Transaction record layout for statements
- `CVACT03Y` - Card cross-reference structure
- `CUSTREC` - Customer record
- `CVACT01Y` - Account record

**Files Accessed**:
- `TRNXFILE` (TRNXFILE) - Transaction data (sequential read via subroutine)
- `XREFFILE` (XREFFILE) - Card/account cross-reference (sequential read)
- `CUSTFILE` (CUSTFILE) - Customer master (random read by customer ID)
- `ACCTFILE` (ACCTFILE) - Account master (random read by account ID)
- `STMT-FILE` (STMTFILE) - Plain text statement output
- `HTML-FILE` (HTMLFILE) - HTML statement output

## Program Relationships
**Calls**: `CBSTM03B` (file I/O subroutine)  
**Called By**: JCL batch job for monthly statement generation (CREASTMT.JCL)

## Notable Patterns

### Legacy Mainframe Techniques (Educational)
1. **Control Block Addressing**: Direct PSA/TCB/TIOT access for job information
2. **ALTER Statement**: Dynamic paragraph flow modification (deprecated pattern)
3. **GO TO Statements**: Non-structured branching for file open sequence
4. **2D Arrays**: Card table with nested transaction table (51×10)
5. **COMP and COMP-3**: Binary and packed decimal for counters and amounts
6. **Subroutine Calls**: All file I/O delegated to CBSTM03B

### Data Formatting
- Uses STRING statements to build customer address from components
- Formats currency amounts with editing (99999999.99-)
- Creates HTML with inline CSS for presentation
- Handles date formatting for statement header

### Memory Efficiency
- Loads entire transaction file into memory array once
- Sequential processing of cross-reference drives statement generation
- Random access to customer/account files for each statement

### Error Handling
- Validates file operation return codes from subroutine
- Displays error messages with return codes
- Abends program (CEE3ABD) on file errors

## Business Rules
1. One statement per card cross-reference entry
2. Transactions organized by card number, then transaction ID
3. Balance and FICO score from account file
4. Customer address formatted with city, state, country, zip
5. Total of all transaction amounts calculated and displayed
6. Dual output: text for printing, HTML for electronic delivery
