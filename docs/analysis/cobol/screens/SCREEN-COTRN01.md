# Screen Analysis: COTRN01

## Overview
**Source File**: `app/bms/COTRN01.bms`  
**Type**: Detail Inquiry  
**Program**: COTRN01C (Transaction Detail View)  
**Map Name**: COTRN1A

## Purpose
Displays complete details for a single transaction including financial data, transaction classification, and merchant information. Pure inquiry screen with no update capability.

## Screen Layout

### Header Section (Lines 1-2)
- Transaction ID: CT01
- Program name: COTRN01C
- Title: "View Transaction" (centered, line 4)
- Current date: MM/DD/YY format
- Current time: HH:MM:SS format

### Input Section (Line 6)
- **TRNIDIN** - Enter Transaction ID (16 chars, green/underlined, required)
- Initial cursor position (IC attribute)

### Detail Display Section (Lines 10-20)
All fields are display-only (ASKIP attribute), organized in logical groups:

**Transaction Identification** (Line 10):
- `TRNID` - Transaction ID (16 chars, blue) - echo of input
- `CARDNUM` - Card Number (16 chars, blue)

**Transaction Classification** (Line 12):
- `TTYPCD` - Type Code (2 chars, blue)
- `TCATCD` - Category Code (4 chars, blue)
- `TRNSRC` - Source (10 chars, blue)

**Transaction Details** (Lines 14-16):
- `TDESC` - Description (60 chars, blue) - full transaction description
- `TRNAMT` - Amount (12 chars, blue) - formatted with sign
- `TORIGDT` - Original Date (10 chars, blue) - timestamp
- `TPROCDT` - Processing Date (10 chars, blue) - timestamp

**Merchant Information** (Lines 18-20):
- `MID` - Merchant ID (9 chars, blue)
- `MNAME` - Merchant Name (30 chars, blue)
- `MCITY` - Merchant City (25 chars, blue)
- `MZIP` - Merchant Zip (10 chars, blue)

### Footer Section (Lines 23-24)
- Error message area (Line 23): `ERRMSG` - 78 chars, red, bright
- Function keys (Line 24): "ENTER=Fetch  F3=Back  F4=Clear  F5=Browse Tran."

## Key Fields

**Input Field**:
- `TRNIDIN` (required) - Transaction ID to lookup (16 chars, numeric)

**Output Fields** (all display-only):
- `TRNNAME` - Transaction ID (CT01)
- `PGMNAME` - Program name (COTRN01C)
- `TITLE01`, `TITLE02` - Screen titles
- `CURDATE` - Current date
- `CURTIME` - Current time
- `TRNID` - Transaction ID (display echo)
- `CARDNUM` - Associated card number
- `TTYPCD` - Transaction type code
- `TCATCD` - Transaction category code
- `TRNSRC` - Transaction source
- `TDESC` - Full description text
- `TRNAMT` - Transaction amount (formatted)
- `TORIGDT` - Original transaction date/time
- `TPROCDT` - Processing date/time
- `MID` - Merchant ID
- `MNAME` - Merchant name
- `MCITY` - Merchant city
- `MZIP` - Merchant zip code
- `ERRMSG` - Error/information messages

## Function Keys

- **Enter**: Look up and display transaction details for entered ID
- **F3**: Return to previous screen (main menu or calling program)
- **F4**: Clear all fields for new search
- **F5**: Return to transaction browse list (COTRN00C)

## Color Scheme

- **Blue**: Static labels, program info, all data display fields
- **Yellow**: Titles, function key help line
- **Green**: Transaction ID input field (underlined)
- **Turquoise**: Field labels (prompts)
- **Red**: Error messages (bright)
- **Neutral**: Section title, separator line

## Navigation Flow

**Entry Points**:
- From transaction list (COTRN00C) - transaction ID pre-populated from selection
- From main menu (COMEN01C) - via direct invocation
- Direct via transaction ID CT01

**Exit Points**:
- F3 → Previous screen (COMEN01C or calling program)
- F5 → Transaction list (COTRN00C)

**Within Screen**:
- Enter Transaction ID → Press Enter → View details
- F4 → Clear screen → Enter new Transaction ID
- F5 → Return to list to select different transaction

## User Interaction Pattern

1. Screen displays with Transaction ID input field (cursor here)
2. User enters transaction ID (or pre-populated from list)
3. User presses Enter
4. System retrieves and displays all transaction details
5. User reviews read-only information
6. User can:
   - Press F4 to clear and search for different transaction
   - Press F5 to return to transaction list
   - Press F3 to return to previous screen/menu
7. No update or modification capability

## Validation

- Transaction ID is required (cannot be empty)
- Transaction ID must exist in TRANSACT file
- If not found, error message: "Transaction ID NOT found..."
- All other fields are display-only, no validation needed

## Display Formatting

- Amount displayed with sign (+ or -) and two decimal places
- Dates displayed as timestamps (YYYY-MM-DD HH:MM:SS format typically)
- All fields left-aligned in their display areas
- Separator line (dashes) divides input from detail sections

## Integration with List Screen

When user selects transaction from COTRN00C:
1. Transaction ID passed in COMMAREA (CDEMO-CT01-TRN-SELECTED)
2. COTRN01C auto-populates TRNIDIN field
3. Auto-executes lookup on first entry
4. Displays transaction without requiring user to press Enter
5. F5 returns to list at same position
