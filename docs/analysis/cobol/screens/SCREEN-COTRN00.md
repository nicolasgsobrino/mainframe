# Screen Analysis: COTRN00

## Overview
**Source File**: `app/bms/COTRN00.bms`  
**Type**: Data Inquiry/List with Selection  
**Program**: COTRN00C (Transaction List)  
**Map Name**: COTRN0A

## Purpose
Displays a paginated list of up to 10 transactions with search capability. Users can browse transactions and select one to view details.

## Screen Layout

### Header Section (Lines 1-2)
- Transaction ID: CT00
- Program name: COTRN00C
- Title: "List Transactions" (centered, line 4)
- Current date: MM/DD/YY format
- Current time: HH:MM:SS format
- Page number indicator (top right)

### Search Section (Line 6)
- **Input Field**:
  - `TRNIDIN` - Search by Transaction ID (16 chars, numeric)
  - Color: Green with underline
  - Optional field

### Transaction List Section (Lines 8-19)
**Column Headers** (Line 8):
- Sel (3 chars) - Selection field
- Transaction ID (16 chars)
- Date (8 chars)
- Description (26 chars)
- Amount (12 chars)

**Data Rows** (Lines 10-19, 10 rows):
Each row contains:
- `SEL000x` - Selection input field (1 char, green/underlined) - accepts 'S' or 's'
- `TRNIDxx` - Transaction ID (16 chars, blue, display only)
- `TDATExx` - Transaction date (8 chars, blue, display only)
- `TDESCxx` - Description (26 chars, blue, display only)
- `TAMTxxx` - Amount (12 chars, blue, display only)

Where x ranges from 01 to 10 for the 10 visible rows.

### Footer Section (Lines 21-24)
- Instructions (Line 21): "Type 'S' to View Transaction details from the list"
- Error message area (Line 23): `ERRMSG` - 78 chars, red, bright
- Function keys (Line 24): "ENTER=Continue  F3=Back  F7=Backward  F8=Forward"

## Key Fields

**Input Fields**:
- `TRNIDIN` (optional) - Transaction ID to search for (starting point)
- `SEL0001` through `SEL0010` - Selection fields for each row (1 char each)

**Output Fields**:
- `TRNNAME` - Transaction ID (CT00)
- `PGMNAME` - Program name (COTRN00C)
- `TITLE01`, `TITLE02` - Screen titles
- `CURDATE` - Current date
- `CURTIME` - Current time
- `PAGENUM` - Current page number
- `TRNIDxx` - Transaction IDs (10 rows)
- `TDATExx` - Transaction dates (10 rows)
- `TDESCxx` - Transaction descriptions (10 rows)
- `TAMTxxx` - Transaction amounts (10 rows)
- `ERRMSG` - Error/information messages

## Function Keys

- **Enter**: Process search or selection
- **F3**: Return to main menu
- **F7**: Page backward (previous 10 transactions)
- **F8**: Page forward (next 10 transactions)

## Color Scheme

- **Blue**: Static labels, program info, data fields
- **Yellow**: Titles
- **Green**: Input fields (underlined)
- **Turquoise**: Search labels, page indicator
- **Red**: Error messages (bright)
- **Neutral**: Column headers, white text

## Navigation Flow

**Entry Points**:
- From main menu (COMEN01C) - transaction inquiry option
- From transaction detail (COTRN01C) - return via F3

**Exit Points**:
- F3 → Main menu (COMEN01C)
- Select transaction ('S') → Transaction detail (COTRN01C)

**Within Screen**:
- Enter with Transaction ID → Search from that ID forward
- F7 → Previous page (if not at top)
- F8 → Next page (if more records available)

## User Interaction Pattern

1. Screen displays with optional search field
2. User can:
   - Leave search blank to see all transactions from beginning
   - Enter Transaction ID to start browsing from that point
   - Type 'S' in any selection field to view that transaction's details
   - Use F7/F8 to navigate pages
   - Press F3 to return to menu
3. Selected transaction opens in detail view (COTRN01C)
4. User can return to same list position

## Validation

- Transaction ID search field accepts only numeric input
- Selection field accepts only 'S' or 's' (case-insensitive)
- Other inputs in selection field generate error message
- Invalid function keys show error message
