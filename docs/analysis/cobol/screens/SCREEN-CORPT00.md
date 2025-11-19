# Screen Analysis: CORPT00

## Overview
**Source File**: `app/bms/CORPT00.bms`  
**Type**: Data Entry/Selection  
**Program**: CORPT00C

## Purpose
Allows users to select and submit transaction reports for batch processing. Provides three report type options (monthly, yearly, custom) with date range input for custom reports and confirmation before job submission.

## Key Fields

### Input Fields
- **MONTHLY**: Single character (checkbox style) - Select monthly report
- **YEARLY**: Single character (checkbox style) - Select yearly report
- **CUSTOM**: Single character (checkbox style) - Select custom report with date range
- **SDTMM**: 2-digit numeric - Start date month (01-12)
- **SDTDD**: 2-digit numeric - Start date day (01-31)
- **SDTYYYY**: 4-digit numeric - Start date year
- **EDTMM**: 2-digit numeric - End date month (01-12)
- **EDTDD**: 2-digit numeric - End date day (01-31)
- **EDTYYYY**: 4-digit numeric - End date year
- **CONFIRM**: Single character (Y/N) - Confirm report submission

### Output Fields
- **TRNNAME**: Transaction ID (CR00)
- **PGMNAME**: Program name (CORPT00C)
- **TITLE01**: Application title
- **TITLE02**: Screen title
- **CURDATE**: Current date (mm/dd/yy)
- **CURTIME**: Current time (hh:mm:ss)
- **ERRMSG**: Error/status messages (78 characters, red)

## Function Keys
- **Enter**: Submit selected report
- **F3**: Return to main menu

## Layout Details

### Report Selection (Lines 7, 9, 11)
```
[ ] Monthly (Current Month)
[ ] Yearly (Current Year)
[ ] Custom (Date Range)
```

### Custom Date Range (Lines 13-14)
```
Start Date : MM/DD/YYYY (MM/DD/YYYY)
  End Date : MM/DD/YYYY (MM/DD/YYYY)
```

### Confirmation (Line 19)
```
The Report will be submitted for printing. Please confirm: _ (Y/N)
```

## Field Attributes
- **Report Selection**: Green underline, IC (initial cursor) on MONTHLY
- **Date Fields**: Green underline, numeric input
- **Confirm Field**: Green underline
- **Labels**: Turquoise for prompts, blue for date format hints
- **Error Messages**: Red, bright
- **Help Text**: Yellow at bottom

## Navigation Flow
- **Entry**: From main menu, cursor on MONTHLY field
- **Processing**: User selects report type → If custom, enter dates → Enter confirmation → Program submits job
- **Success**: Display success message, remain on screen
- **Error**: Display error message, cursor to error field
- **Exit**: F3 returns to main menu (COMEN01C)

## Validation
1. Must select at least one report type
2. If custom selected, all date fields required
3. Dates must be valid calendar dates
4. Confirmation required before submission
5. Only Y/N accepted for confirmation
