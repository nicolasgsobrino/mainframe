# Screen Analysis: COTRN02

## Overview
**Source File**: `app/bms/COTRN02.bms`  
**Type**: Data Entry Form  
**Program**: COTRN02C (Add Transaction)  
**Map Name**: COTRN2A

## Purpose
Provides a data entry form to add new transactions to the system. Collects all required transaction information including account/card, transaction classification, amounts, dates, and merchant information. Requires user confirmation before committing.

## Screen Layout

### Header Section (Lines 1-2)
- Transaction ID: CT02
- Program name: COTRN02C
- Title: "Add Transaction" (centered, line 4)
- Current date: MM/DD/YY format
- Current time: HH:MM:SS format

### Key Input Section (Line 6)
**Account or Card Entry** (mutually exclusive):
- `ACTIDIN` - Enter Account # (11 digits, green/underlined)
- "(or)" separator
- `CARDNIN` - Card # (16 digits, green/underlined)
- User provides one or the other, system cross-references to find other value

### Transaction Detail Input Section (Lines 10-18)
All fields are input-enabled (green with underline):

**Line 10 - Transaction Classification**:
- `TTYPCD` - Type Code (2 chars, numeric)
- `TCATCD` - Category Code (4 chars, numeric)
- `TRNSRC` - Source (10 chars)

**Line 12 - Description**:
- `TDESC` - Description (60 chars, full width)

**Line 14 - Financial and Temporal Data**:
- `TRNAMT` - Amount (12 chars, format: -99999999.99)
- `TORIGDT` - Original Date (10 chars, format: YYYY-MM-DD)
- `TPROCDT` - Processing Date (10 chars, format: YYYY-MM-DD)

**Line 15 - Format Helpers** (display only, blue):
- "(-99999999.99)" - amount format example
- "(YYYY-MM-DD)" - date format examples (2)

**Lines 16-18 - Merchant Information**:
- `MID` - Merchant ID (9 chars, numeric)
- `MNAME` - Merchant Name (30 chars)
- `MCITY` - Merchant City (25 chars)
- `MZIP` - Merchant Zip (10 chars)

### Confirmation Section (Line 21)
- Prompt: "You are about to add this transaction. Please confirm :"
- `CONFIRM` - Confirmation field (1 char, Y/N)
- "(Y/N)" prompt

### Footer Section (Lines 23-24)
- Error message area (Line 23): `ERRMSG` - 78 chars, red/bright (turns green on success)
- Function keys (Line 24): "ENTER=Continue  F3=Back  F4=Clear  F5=Copy Last Tran."

## Key Fields

**Input Fields** (all required unless noted):
- `ACTIDIN` - Account ID (11 digits, provide this OR card number)
- `CARDNIN` - Card Number (16 digits, provide this OR account ID)
- `TTYPCD` - Transaction Type Code (2 digits)
- `TCATCD` - Transaction Category Code (4 digits)
- `TRNSRC` - Transaction Source (10 chars)
- `TDESC` - Description (60 chars)
- `TRNAMT` - Amount (12 chars with sign)
- `TORIGDT` - Original Date (10 chars, YYYY-MM-DD)
- `TPROCDT` - Processing Date (10 chars, YYYY-MM-DD)
- `MID` - Merchant ID (9 digits)
- `MNAME` - Merchant Name (30 chars)
- `MCITY` - Merchant City (25 chars)
- `MZIP` - Merchant Zip (10 chars)
- `CONFIRM` - Confirmation (1 char, Y or N)

**Output Fields**:
- `TRNNAME` - Transaction ID (CT02)
- `PGMNAME` - Program name (COTRN02C)
- `TITLE01`, `TITLE02` - Screen titles
- `CURDATE` - Current date
- `CURTIME` - Current time
- `ERRMSG` - Error/success messages

## Function Keys

- **Enter**: Validate inputs and add transaction (requires confirmation Y)
- **F3**: Return to previous screen/main menu (discard entry)
- **F4**: Clear all fields (start fresh entry)
- **F5**: Copy last transaction data for entered account/card

## Color Scheme

- **Blue**: Static labels, program info, format examples
- **Yellow**: Titles, function key help line
- **Green**: All input fields (underlined)
- **Turquoise**: Field labels/prompts
- **Red**: Error messages (bright)
- **Green**: Success messages (changes from red)
- **Neutral**: Section title, instructions

## Navigation Flow

**Entry Points**:
- From main menu (COMEN01C)
- Direct via transaction ID CT02

**Exit Points**:
- F3 → Previous screen/main menu
- After successful add → Screen clears for next entry

**Within Screen**:
- Fill in Account ID or Card Number
- System auto-fills the other via cross-reference
- Enter all transaction details
- Enter 'Y' in confirmation field
- Press Enter → Transaction added
- F5 → Copy last transaction data (shortcut for similar entries)
- F4 → Clear and start over

## User Interaction Pattern

1. Screen displays empty form, cursor on Account ID field
2. User enters Account ID or Card Number
3. System validates and cross-references to populate other field
4. User enters transaction details (or presses F5 to copy last transaction)
5. User reviews entered data
6. User enters 'Y' in confirmation field
7. User presses Enter
8. System validates all fields
9. If valid, writes transaction and displays success with new Transaction ID
10. Form clears for next entry
11. User repeats or exits with F3

## Validation

### Required Fields
All fields marked above are required - system validates presence

### Format Validation
- Account ID: numeric, 11 digits
- Card Number: numeric, 16 digits
- Type Code: numeric, 2 digits
- Category Code: numeric, 4 digits
- Amount: signed numeric with decimal (-99999999.99)
- Origin Date: YYYY-MM-DD format, valid calendar date
- Processing Date: YYYY-MM-DD format, valid calendar date
- Merchant ID: numeric, 9 digits

### Business Validation
- Account ID must exist in system (CXACAIX lookup)
- Card Number must exist in system (CCXREF lookup)
- Account and Card must match (cross-reference validation)
- Dates must be actual valid calendar dates (CSUTLDTC validation)
- Confirmation must be Y or N (case-insensitive)

### Error Messages
- Specific error for each validation failure
- Cursor positioned to error field
- Error displayed in red at bottom

### Success Message
- Green message with generated Transaction ID
- Example: "Transaction added successfully. Your Tran ID is 0000000000000123."

## Format Helpers
The screen shows format examples directly below input fields:
- Amount format: (-99999999.99)
- Date formats: (YYYY-MM-DD) - shown for both origin and process dates

These help users enter data correctly without needing external documentation.

## Productivity Features

### Copy Last Transaction (F5)
- Retrieves most recent transaction for entered account/card
- Pre-fills all transaction data fields
- User can modify as needed
- Still requires confirmation
- Speeds repetitive data entry

### Smart Cross-Reference
- Enter only Account ID → Card Number auto-filled
- Enter only Card Number → Account ID auto-filled
- Reduces data entry burden
- Validates account/card relationship
