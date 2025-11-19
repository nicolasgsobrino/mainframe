# Program Analysis: COCRDUPC

## Overview
**Source File**: `app/cbl/COCRDUPC.cbl`
**Type**: Online Transaction - CICS
**Module**: Card Management - Update

## Business Purpose
COCRDUPC manages credit card information updates with comprehensive validation and data integrity controls. It implements a secure multi-step update process that ensures data consistency and prevents concurrent modification conflicts. This program is critical for maintaining accurate card information in the system.

The program enables authorized users to:
- Update card embossed name (as printed on physical card)
- Change card active status (activate or deactivate cards)
- Modify card expiration date
- Maintain data integrity through validation and optimistic locking

## Key Logic

### Processing Flow (Multi-Step State Machine)
The program implements a sophisticated multi-step workflow:

1. **Step 1: Initial Entry**
   - Receives control from COCRDLIC with account ID and card number
   - Reads CARDDAT using READ UPDATE (locks record)
   - Displays current card values on screen
   - Waits for user modifications

2. **Step 2: Field Validation**
   - User modifies fields and presses Enter
   - Program validates all changed fields
   - If validation fails: displays error, repositions cursor, returns to edit mode
   - If validation succeeds: displays confirmation message, reveals F5/F12 options

3. **Step 3: Confirmation**
   - **F5 (Save)**: Proceeds to Step 4
   - **F12 (Cancel)**: Releases lock, returns to card list or edit mode
   - **F3 (Exit)**: Releases lock, returns to card list

4. **Step 4: Commit**
   - Checks if record has been modified by another user (optimistic locking)
   - If conflict detected: displays error, re-reads record, returns to edit mode
   - If no conflict: executes REWRITE to update CARDDAT
   - Releases lock and returns to COCRDLIC with success message

### Validation Rules

**Card Name (CRDNAME) Validation**:
- Must be alphabetic characters and spaces only
- No numbers, no special characters
- Maximum 50 characters
- Cannot be blank
- COBOL: `IF CRDNAME NOT ALPHABETIC`

**Active Status (CRDSTCD) Validation**:
- Must be exactly 'Y' or 'N' (case sensitive)
- COBOL: `IF CRDSTCD NOT = 'Y' AND NOT = 'N'`

**Expiration Month (EXPMON) Validation**:
- Must be numeric
- Must be in range 01-12
- COBOL: `IF EXPMON NOT NUMERIC OR EXPMON < 1 OR EXPMON > 12`

**Expiration Year (EXPYEAR) Validation**:
- Must be numeric
- Must be in range 1950-2099 (business rule for valid credit card years)
- Cannot be in the past (compared to current date)
- COBOL: `IF EXPYEAR NOT NUMERIC OR EXPYEAR < 1950 OR EXPYEAR > 2099`

**Expiration Date Logic**:
- Combined month/year must not be expired
- Program calculates expiration day (typically last day of month)
- Compares full expiration date to current date

### Optimistic Locking Implementation

The program uses CICS file control features for concurrency management:

1. **READ UPDATE**: Initial read locks the record for this transaction
2. **Version Check**: Program stores original record content or timestamp
3. **Pre-REWRITE Check**: Before updating, verifies record hasn't changed
4. **Conflict Detection**: If record modified by another user, abort update
5. **REWRITE**: Updates record only if no conflict detected
6. **Lock Release**: Automatically released after REWRITE or UNLOCK command

Error handling for concurrent updates:
- If REWRITE fails with "record changed" condition
- Display user-friendly message: "Card updated by another user"
- Re-read current record values
- Allow user to retry with latest data

### Screen State Management
Program maintains multiple states across pseudo-conversations:
- **INITIAL**: First display of card data
- **EDIT**: User modifying fields
- **VALIDATE**: Checking field values
- **CONFIRM**: Awaiting Save/Cancel decision
- **COMMIT**: Writing changes to database
- **ERROR**: Displaying validation or concurrency errors

State transitions tracked in COMMAREA to preserve context between interactions.

## Data Dependencies

**Key Copybooks**:
- `CVCRD01Y` - Card master record layout (card number, account ID, CVV, embossed name, expiration date, active status)
- `CVACT02Y` - Account-to-card cross-reference for validation
- `CVCUS01Y` - Customer information for additional context
- `CSMSG02Y` - Standard message definitions for errors and abend handling
- `COCOM01Y` - Communication area for state management across pseudo-conversations
- `COCRDUP` (generated from BMS) - Screen map structure for card update display

**Files Accessed**:
- `CARDDAT` (Read Update, Rewrite) - VSAM KSDS indexed by card number
  - READ UPDATE: Locks record during update process
  - REWRITE: Commits changes to file
  - UNLOCK: Releases lock if update cancelled

**Screens**:
- `COCRDUP` - Card update screen with editable fields and confirmation workflow

## Program Relationships

**Called By**: 
- `COCRDLIC` - Card list program (via XCTL when user selects 'U' for update)
- COMMAREA contains selected account ID and card number

**Calls/Transfers To**: 
- `COCRDLIC` - Returns to card list after successful update or cancel
- May call `CSMSG02Y` message formatting routines
- May call abend handling routines if critical error occurs

**Integration Points**:
- Receives card identification via COMMAREA
- Updates shared CARDDAT file (impacts all card inquiry/update programs)
- May trigger downstream processes (audit logging, notifications)

## Notable Patterns

### Multi-Step Update Pattern
This program exemplifies the classic CICS update pattern:
1. Read and lock
2. Display to user
3. Collect changes
4. Validate
5. Confirm
6. Check for concurrent updates
7. Commit or rollback

This pattern is essential for data integrity in pseudo-conversational environments where locks cannot be held across user think time.

### Field-Level Validation
Each field has explicit validation logic with specific error messages. This provides:
- Clear user feedback (which field is wrong, why it's wrong)
- Cursor repositioning to error field
- Prevents invalid data from reaching database

### Optimistic Concurrency Control
Rather than holding locks during user think time (pessimistic locking), the program:
- Releases locks between pseudo-conversations
- Checks for conflicts before final commit
- Handles conflicts gracefully with re-read and retry

This approach maximizes system concurrency while maintaining data consistency.

### Defensive Programming
Program includes extensive error handling:
- HANDLE CONDITION for CICS errors (NOTFND, IOERR, DUPKEY)
- Validation before database operations
- Verification after database operations
- User-friendly error messages (not technical error codes)
- Fallback to abend handler for unexpected conditions

## Modernization Considerations

### .NET Migration

**File Operations → Entity Framework**:
```csharp
// Replace READ UPDATE + REWRITE pattern
public async Task<bool> UpdateCardAsync(Card card)
{
    using var transaction = await _context.Database.BeginTransactionAsync();
    try
    {
        var existingCard = await _context.Cards
            .FirstOrDefaultAsync(c => c.CardNumber == card.CardNumber);
        
        if (existingCard == null)
            throw new NotFoundException("Card not found");
        
        // Optimistic concurrency check using RowVersion
        existingCard.EmbossedName = card.EmbossedName;
        existingCard.ActiveStatus = card.ActiveStatus;
        existingCard.ExpirationMonth = card.ExpirationMonth;
        existingCard.ExpirationYear = card.ExpirationYear;
        
        await _context.SaveChangesAsync(); // Throws DbUpdateConcurrencyException on conflict
        await transaction.CommitAsync();
        return true;
    }
    catch (DbUpdateConcurrencyException)
    {
        await transaction.RollbackAsync();
        return false; // Handle conflict in controller
    }
}
```

**Validation → FluentValidation or Data Annotations**:
```csharp
public class CardUpdateValidator : AbstractValidator<CardUpdateDto>
{
    public CardUpdateValidator()
    {
        RuleFor(x => x.EmbossedName)
            .NotEmpty()
            .MaximumLength(50)
            .Matches(@"^[a-zA-Z\s]+$")
            .WithMessage("Card name must contain only letters and spaces");
        
        RuleFor(x => x.ActiveStatus)
            .Must(x => x == "Y" || x == "N")
            .WithMessage("Status must be Y or N");
        
        RuleFor(x => x.ExpirationMonth)
            .InclusiveBetween(1, 12)
            .WithMessage("Month must be between 1 and 12");
        
        RuleFor(x => x.ExpirationYear)
            .InclusiveBetween(1950, 2099)
            .WithMessage("Year must be between 1950 and 2099")
            .Must(BeValidExpirationDate)
            .WithMessage("Expiration date cannot be in the past");
    }
    
    private bool BeValidExpirationDate(CardUpdateDto dto, int year)
    {
        var expiry = new DateTime(year, dto.ExpirationMonth, 
            DateTime.DaysInMonth(year, dto.ExpirationMonth));
        return expiry >= DateTime.Today;
    }
}
```

**Screen Handling → MVC/API**:
```csharp
[HttpPut("api/cards/{accountId}/{cardNumber}")]
public async Task<IActionResult> UpdateCard(
    string accountId, 
    string cardNumber, 
    [FromBody] CardUpdateDto card)
{
    var validator = new CardUpdateValidator();
    var validationResult = await validator.ValidateAsync(card);
    
    if (!validationResult.IsValid)
        return BadRequest(validationResult.Errors);
    
    var success = await _cardService.UpdateCardAsync(card);
    
    if (!success)
        return Conflict(new { message = "Card was modified by another user" });
    
    return Ok(new { message = "Card updated successfully" });
}
```

### Architecture Impact
- CICS transaction → Web API endpoint (PUT method)
- Multi-step screen flow → Single API call with client-side confirmation
- COMMAREA state → JWT token or session for authentication/authorization
- Optimistic locking → EF Core RowVersion/Timestamp column
- Pseudo-conversational → Stateless HTTP with idempotent operations

### UI/UX Improvements
- Real-time validation with immediate visual feedback
- Disable Save button until all validations pass
- Show change summary before commit ("You are changing: Name from 'John Smith' to 'John Q. Smith'")
- Optimistic UI: Update interface immediately, rollback on conflict
- Toast notifications for success/error instead of screen messages
- Undo capability (store previous values, allow revert)

### Security Enhancements
- **Authentication**: Verify user identity (JWT token, OAuth)
- **Authorization**: Check user has permission to update this card
- **Audit Trail**: Log all changes with user ID, timestamp, before/after values
- **Field-Level Security**: Some users can view but not modify certain fields
- **Data Masking**: Mask CVV in logs and audit trails

### Testing Strategy
- **Unit Tests**: Validation logic, business rules
- **Integration Tests**: Database operations, concurrency handling
- **Concurrency Tests**: Simulate simultaneous updates, verify conflict detection
- **Security Tests**: Authorization enforcement, audit logging
- **UI Tests**: Form validation, error display, success flow
- **Performance Tests**: Update latency under load, lock contention scenarios

### Concurrency Testing
Critical to verify optimistic locking works correctly:
```csharp
[Fact]
public async Task UpdateCard_ConcurrentUpdate_DetectsConflict()
{
    // Arrange: Two transactions read same card
    var card1 = await _context.Cards.FirstAsync(c => c.CardNumber == "4123...");
    var card2 = await _context.Cards.FirstAsync(c => c.CardNumber == "4123...");
    
    // Act: First update succeeds
    card1.EmbossedName = "Updated Name 1";
    await _context.SaveChangesAsync();
    
    // Second update should fail
    card2.EmbossedName = "Updated Name 2";
    
    // Assert: DbUpdateConcurrencyException thrown
    await Assert.ThrowsAsync<DbUpdateConcurrencyException>(
        async () => await _context.SaveChangesAsync());
}
```
