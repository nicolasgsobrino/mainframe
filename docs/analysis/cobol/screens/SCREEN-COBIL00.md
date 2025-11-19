# Screen Analysis: COBIL00

## Overview
**Source File**: `app/bms/COBIL00.bms`  
**Type**: Data Entry/Payment  
**Program**: COBIL00C

## Purpose
Enables customers to pay their full account balance online. Simple interface showing current balance and requiring confirmation before processing the payment.

## Key Fields

### Input Fields
- **ACTIDIN**: Account ID (11 digits) - Account to pay
- **CONFIRM**: Single character (Y/N) - Confirm payment

### Output Fields
- **TRNNAME**: Transaction ID (CB00)
- **PGMNAME**: Program name (COBIL00C)
- **TITLE01**: Application title
- **TITLE02**: Screen title
- **CURDATE**: Current date (mm/dd/yy)
- **CURTIME**: Current time (hh:mm:ss)
- **CURBAL**: Current account balance (14 characters, formatted)
- **ERRMSG**: Error/status messages (78 characters, red)

## Function Keys
- **Enter**: Process payment (after confirmation)
- **F3**: Return to previous screen
- **F4**: Clear current screen

## Layout Details

### Account Entry (Line 6)
```
Enter Acct ID: ___________
```

### Balance Display (Line 11)
```
Your current balance is: $99,999,999.99
```
(Displayed after valid account ID entered)

### Payment Confirmation (Line 15)
```
Do you want to pay your balance now. Please confirm: _ (Y/N)
```

## Field Attributes
- **ACTIDIN**: Green underline, IC (initial cursor)
- **CURBAL**: Blue, output only, right-aligned currency format
- **CONFIRM**: Green underline
- **Labels**: Turquoise for prompts
- **Separator**: Yellow dashed line (line 8)
- **Error Messages**: Red, bright
- **Help Text**: Yellow at bottom

## Navigation Flow
- **Entry**: User enters account ID → Press Enter
- **Display**: Program shows current balance
- **Confirm**: User enters Y to confirm, N to cancel
- **Success**: Display success message with transaction ID
- **Error**: Display error message (account not found, zero balance, etc.)
- **Exit**: F3 returns to previous screen, F4 clears and restarts

## Payment Process
1. Enter account ID and press Enter
2. System displays current balance
3. User enters Y to confirm payment
4. System creates payment transaction
5. System updates account balance to zero
6. Success message displays with transaction ID

## Validation
1. Account ID cannot be empty
2. Account must exist in system
3. Balance must be greater than zero
4. Confirmation required (Y/N only)
5. Y confirms payment, N cancels and clears screen
