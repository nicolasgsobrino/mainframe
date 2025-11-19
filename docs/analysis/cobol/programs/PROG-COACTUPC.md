# Program Analysis: COACTUPC

## Overview
**Source File**: `app/cbl/COACTUPC.cbl`
**Type**: Online Transaction - CICS (4,237 lines - largest analyzed program)
**Module**: Account and Customer Management - Comprehensive Update

## Business Purpose
COACTUPC is the most complex program in the Card Demo application, providing comprehensive update capabilities for both account and customer information in a single integrated transaction. This program is critical for maintaining data integrity across two related master files (ACCTDAT and CUSTDAT) with transactional consistency.

The program enables authorized users to:
- Update account information (status, limits, balances, dates, group ID)
- Update customer personal information (name, SSN, DOB, FICO score)
- Update customer address and contact details (address, phone, government ID, EFT account)
- Maintain referential integrity between account and customer records
- Ensure transactional consistency across multiple file updates

This is an enterprise-grade update program demonstrating mainframe best practices for complex data maintenance with extensive validation.

## Key Logic

### Processing Flow (Multi-Step State Machine)
The program implements an extremely sophisticated workflow with 7+ distinct states:

1. **ACUP-DETAILS-NOT-FETCHED**: Initial state, prompting for account number
2. **ACUP-SHOW-DETAILS**: Account/customer data loaded and displayed for editing
3. **ACUP-CHANGES-NOT-OK**: User made changes but validation failed
4. **ACUP-CHANGES-OK-NOT-CONFIRMED**: Changes validated, awaiting F5 confirmation
5. **ACUP-CHANGES-OKAYED-AND-DONE**: Update completed successfully
6. **ACUP-CHANGES-OKAYED-LOCK-ERROR**: Could not acquire record locks
7. **ACUP-CHANGES-OKAYED-BUT-FAILED**: Update failed after locking

### File Reading Strategy
Uses a three-step read process to load related data:
1. Read CARDXREF file by account ID to get customer ID and card number
2. Read ACCTDAT file by account ID for account master data
3. Read CUSTDAT file by customer ID for customer master data

All three files must be successfully read to display the complete screen.

### Validation Framework (30+ Validation Routines)
The program contains an extensive validation library with specialized routines:

**Alpha/Alphanumeric Validation**:
- `1220-EDIT-ALPHA-REQD`: Required alphabetic field
- `1230-EDIT-ALPHANUM-REQD`: Required alphanumeric field
- `1235-EDIT-ALPHA-OPT`: Optional alphabetic field
- `1240-EDIT-ALPHANUM-OPT`: Optional alphanumeric field

**Numeric Validation**:
- `1245-EDIT-NUM-REQD`: Required numeric field (must be non-zero)
- `1250-EDIT-SIGNED-9V2`: Signed decimal currency validation using NUMVAL-C

**Specialized Validation**:
- `1260-EDIT-US-PHONE-NUM`: US phone format (area code, prefix, line number)
- `1265-EDIT-US-SSN`: Social Security Number (three parts with specific rules)
- `1270-EDIT-US-STATE-CD`: Valid US state code validation using CSLKPCDY lookup
- `1275-EDIT-FICO-SCORE`: FICO score range (300-850)
- `1280-EDIT-US-STATE-ZIP-CD`: State/ZIP code combination validation

**Date Validation**:
- Uses CSUTLDWY date utility copybook for complex date logic
- Validates year (1900-2099), month (01-12), day (based on month/year)
- Checks for logical date relationships (expiry >= opened, reissue >= opened)

### Currency Handling
- Uses NUMVAL-C function to parse formatted currency input ($12,345.67)
- Supports negative values for debit amounts
- Converts between display format (X with $ and commas) and computational format (S9(9)V99 COMP-3)

### US Phone Number Validation Logic
Comprehensive validation for North American phone format:
1. **Area Code** (first 3 digits):
   - Must be numeric and non-zero
   - Must be valid general-purpose area code (uses lookup table)
   - Cannot be 000 or certain reserved codes
   
2. **Prefix** (middle 3 digits):
   - Must be numeric and non-zero
   
3. **Line Number** (last 4 digits):
   - Must be numeric and non-zero

Formats as: (AAA)BBB-CCCC for storage

### SSN Validation Rules
Three-part validation matching SSN format XXX-XX-XXXX:
- **Part 1 (3 digits)**: Cannot be 000, 666, or 900-999 (reserved/invalid ranges)
- **Part 2 (2 digits)**: Must be 01-99 (cannot be 00)
- **Part 3 (4 digits)**: Must be 0001-9999 (cannot be 0000)

### State and ZIP Code Validation
- Uses CSLKPCDY copybook with lookup tables for valid US state codes
- Implements crude but effective state/ZIP validation by checking first 2 digits of ZIP against state
- Example: California (CA) ZIPs start with 90-96

### Optimistic Locking Implementation
Sophisticated two-file concurrency control:

1. **Initial Read**: Standard READ to fetch and display data, stores original values
2. **Lock Acquisition**: READ UPDATE on both ACCTDAT and CUSTDAT before commit
3. **Change Detection**: Comprehensive field-by-field comparison (section 9700):
   - Compares ALL account fields against original values
   - Compares ALL customer fields against original values
   - Uses UPPER-CASE/LOWER-CASE functions for case-insensitive string comparisons
   - If ANY field changed: abort update, display "Data was changed" message
4. **Commit**: REWRITE both files if no conflicts detected
5. **Rollback**: SYNCPOINT ROLLBACK if either update fails

### Two-Phase Commit Pattern
Update sequence with rollback capability:
```cobol
EXEC CICS REWRITE FILE(ACCTDAT) ... END-EXEC
IF SUCCESS
   EXEC CICS REWRITE FILE(CUSTDAT) ... END-EXEC
   IF FAIL
      EXEC CICS SYNCPOINT ROLLBACK END-EXEC
   END-IF
END-IF
```

This ensures atomicity: either both files update or neither updates.

### Change Detection Logic
The program employs extensive field-by-field comparison before update:
- Account fields: status, balances, limits, dates (broken into year/month/day), group
- Customer fields: name parts, address lines, city, state, ZIP, country, phones, SSN, DOB, FICO, government ID, EFT account, primary holder flag
- Uses FUNCTION UPPER-CASE for case-insensitive string comparisons
- Total of 30+ individual field comparisons

If ANY field differs from original value stored when screen was displayed, the program rejects the update with message "Data was changed by another user" and reloads current values.

## Data Dependencies

**Key Copybooks**:
- `CVACT01Y` - Account master record layout
- `CVCUS01Y` - Customer master record layout
- `CVACT03Y` - Card cross-reference (account to customer to card)
- `COCOM01Y` - Communication area for state management
- `CSUTLDWY` - Date utility routines (validation, formatting, calculations)
- `CSLKPCDY` - Lookup code tables (state codes, area codes, validation lists)
- `CSMSG02Y` - Standard message definitions and abend handling
- `CSSETATY` - Screen attribute setting macro (used via COPY REPLACING for 40+ fields)
- `COACTUP` (generated from BMS) - Complex screen map structure with 40+ input fields

**Files Accessed**:
- `CARDXREF` (Read) - Card cross-reference indexed by account ID (alternate index)
- `ACCTDAT` (Read, Read Update, Rewrite) - Account master file indexed by account ID
- `CUSTDAT` (Read, Read Update, Rewrite) - Customer master file indexed by customer ID

**Screens**:
- `COACTUP` - Comprehensive account and customer update screen (most complex screen in application)

## Program Relationships

**Called By**: 
- Account list/search programs
- Main menu (account management option)
- Direct transaction invocation with account number

**Calls/Transfers To**: 
- Returns to calling program after successful update or cancel
- May call CSMSG02Y message formatting routines
- Calls abend handler on critical errors

**Integration Points**:
- Updates two master files transactionally
- Maintains referential integrity via CARDXREF lookup
- Coordinates with date utilities (CSUTLDWY) and lookup tables (CSLKPCDY)

## Notable Patterns

### Macro-Based Field Processing
Uses COPY REPLACING extensively for repetitive field attribute setting:
```cobol
COPY CSSETATY REPLACING
  ==(TESTVAR1)== BY ==ACCT-STATUS==
  ==(SCRNVAR2)== BY ==ACSTTUS==
  ==(MAPNAME3)== BY ==CACTUPA==
```

This pattern is applied to 40+ fields, dramatically reducing code duplication. The CSSETATY copybook contains template logic for:
- Setting field colors based on validation status (red for errors)
- Displaying asterisk (*) for blank required fields
- Standardized error highlighting

### Comprehensive Validation Library
The program contains 10+ reusable validation paragraphs that can be called with parameters:
- Move field name to `WS-EDIT-VARIABLE-NAME`
- Move field value to appropriate edit variable
- Perform validation paragraph
- Check result flags and proceed accordingly

This creates a validation framework used throughout the program.

### Change Detection Middleware
Before committing updates, the program implements sophisticated optimistic concurrency:
- Stores original values when record first displayed
- Re-reads with UPDATE lock before commit
- Compares ALL fields between original and current
- Rejects update if any discrepancy found

This is enterprise-grade data integrity protection.

### Complex State Management
Program state tracked via 88-level condition names:
- `ACUP-DETAILS-NOT-FETCHED`
- `ACUP-SHOW-DETAILS`
- `ACUP-CHANGES-MADE`
- `ACUP-CHANGES-NOT-OK`
- `ACUP-CHANGES-OK-NOT-CONFIRMED`
- `ACUP-CHANGES-OKAYED-AND-DONE`
- `ACUP-CHANGES-OKAYED-LOCK-ERROR`
- `ACUP-CHANGES-OKAYED-BUT-FAILED`

State transitions carefully managed in section 2000-DECIDE-ACTION.

### Dynamic Screen Control
Function key visibility controlled programmatically:
- F5 (Save) and F12 (Cancel) hidden initially
- Revealed only after successful validation (ACUP-CHANGES-OK-NOT-CONFIRMED state)
- Implemented via DFHBMDAR (dark) and DFHBMASB (visible bright) attributes

### Two-File Transactional Update
Demonstrates proper CICS transaction management:
1. Lock both records (READ UPDATE)
2. Validate no conflicts
3. Update first file (ACCTDAT)
4. If success, update second file (CUSTDAT)
5. If second fails, SYNCPOINT ROLLBACK to undo first

This ensures atomicity across multiple file updates.

## Modernization Considerations

### .NET Migration

**Multi-File Transaction → Unit of Work Pattern**:
```csharp
public async Task<UpdateResult> UpdateAccountAndCustomerAsync(
    AccountUpdateDto accountUpdate,
    CustomerUpdateDto customerUpdate)
{
    using var transaction = await _context.Database.BeginTransactionAsync();
    try
    {
        // 1. Load entities with row version for optimistic concurrency
        var account = await _context.Accounts
            .FirstOrDefaultAsync(a => a.AccountId == accountUpdate.AccountId);
        var customer = await _context.Customers
            .FirstOrDefaultAsync(c => c.CustomerId == account.CustomerId);
        
        if (account == null || customer == null)
            throw new NotFoundException();
        
        // 2. Apply updates
        _mapper.Map(accountUpdate, account);
        _mapper.Map(customerUpdate, customer);
        
        // 3. Save changes (optimistic concurrency check happens here)
        await _context.SaveChangesAsync();
        
        // 4. Commit transaction
        await transaction.CommitAsync();
        
        return UpdateResult.Success();
    }
    catch (DbUpdateConcurrencyException)
    {
        await transaction.RollbackAsync();
        return UpdateResult.ConcurrencyConflict();
    }
    catch (Exception ex)
    {
        await transaction.RollbackAsync();
        return UpdateResult.Failure(ex.Message);
    }
}
```

**Validation Framework → FluentValidation**:
```csharp
public class AccountUpdateValidator : AbstractValidator<AccountUpdateDto>
{
    public AccountUpdateValidator()
    {
        // Account status
        RuleFor(x => x.ActiveStatus)
            .Must(x => x == "Y" || x == "N")
            .WithMessage("Status must be Y or N");
        
        // Credit limit
        RuleFor(x => x.CreditLimit)
            .GreaterThanOrEqualTo(0)
            .LessThanOrEqualTo(999999.99m);
        
        // Credit limit >= current balance
        RuleFor(x => x)
            .Must(x => x.CreditLimit >= x.CurrentBalance)
            .WithMessage("Credit limit must be >= current balance");
        
        // Dates
        RuleFor(x => x.OpenedDate)
            .LessThanOrEqualTo(x => x.ExpiryDate)
            .WithMessage("Opened date must be before expiry");
        
        RuleFor(x => x.ReissueDate)
            .GreaterThanOrEqualTo(x => x.OpenedDate)
            .When(x => x.ReissueDate.HasValue);
    }
}

public class CustomerUpdateValidator : AbstractValidator<CustomerUpdateDto>
{
    private readonly ILookupService _lookupService;
    
    public CustomerUpdateValidator(ILookupService lookupService)
    {
        _lookupService = lookupService;
        
        // Names
        RuleFor(x => x.FirstName)
            .NotEmpty()
            .MaximumLength(25)
            .Matches(@"^[a-zA-Z\s]+$")
            .WithMessage("First name must contain only letters");
        
        RuleFor(x => x.LastName)
            .NotEmpty()
            .MaximumLength(25)
            .Matches(@"^[a-zA-Z\s]+$");
        
        // SSN
        RuleFor(x => x.SSN)
            .NotEmpty()
            .Matches(@"^\d{3}-\d{2}-\d{4}$")
            .Must(BeValidSSN)
            .WithMessage("Invalid SSN format or reserved number");
        
        // Date of birth - must be 18+ years old
        RuleFor(x => x.DateOfBirth)
            .LessThan(DateTime.Today.AddYears(-18))
            .WithMessage("Customer must be at least 18 years old");
        
        // FICO score
        RuleFor(x => x.FICOScore)
            .InclusiveBetween(300, 850)
            .When(x => x.FICOScore.HasValue);
        
        // US State code
        RuleFor(x => x.State)
            .Must(BeValidStateCode)
            .WithMessage("Invalid US state code");
        
        // ZIP code
        RuleFor(x => x.ZipCode)
            .Matches(@"^\d{5}$")
            .Must((customer, zip) => _lookupService.IsValidStateZipCombo(customer.State, zip))
            .WithMessage("Invalid ZIP code for state");
        
        // Phone numbers
        RuleFor(x => x.Phone1)
            .Matches(@"^\(\d{3}\)\d{3}-\d{4}$")
            .Must(BeValidUSPhone)
            .When(x => !string.IsNullOrEmpty(x.Phone1));
    }
    
    private bool BeValidSSN(string ssn)
    {
        var parts = ssn.Split('-');
        var area = int.Parse(parts[0]);
        return area != 0 && area != 666 && area < 900;
    }
    
    private bool BeValidStateCode(string state)
    {
        return _lookupService.IsValidUSState(state);
    }
    
    private bool BeValidUSPhone(string phone)
    {
        var digits = new string(phone.Where(char.IsDigit).ToArray());
        var areaCode = int.Parse(digits.Substring(0, 3));
        return _lookupService.IsValidGeneralPurposeAreaCode(areaCode);
    }
}
```

**Optimistic Concurrency → EF Core RowVersion**:
```csharp
public class Account
{
    public long AccountId { get; set; }
    
    [Timestamp]
    public byte[] RowVersion { get; set; }  // Automatically checked by EF
    
    // ... other properties
}

public class Customer
{
    public long CustomerId { get; set; }
    
    [Timestamp]
    public byte[] RowVersion { get; set; }
    
    // ... other properties
}
```

EF Core automatically:
- Includes RowVersion in WHERE clause of UPDATE
- Throws `DbUpdateConcurrencyException` if row modified
- No need for manual field-by-field comparison

### Architecture Impact
- Single monolithic CICS transaction → Multiple API endpoints or orchestrated service
- Split into smaller operations: `UpdateAccount`, `UpdateCustomer`, `UpdateAccountAndCustomer`
- 40+ field screen → Tabbed UI or multi-step wizard
- File I/O → Database operations with Entity Framework
- COMMAREA state → Session state or JWT claims
- Pseudo-conversational → Stateless REST API with optimistic concurrency tokens

### API Design
```
PATCH /api/accounts/{accountId}
PATCH /api/customers/{customerId}
PUT /api/accounts/{accountId}/full  (atomic update of account + customer)
```

Include ETag header for optimistic concurrency:
```
Request:
  If-Match: "abc123..."
  
Response (conflict):
  HTTP 412 Precondition Failed
  ETag: "xyz789..."  (current version)
```

### UI/UX Improvements
- **Progressive Disclosure**: Start with key fields, expand to full form
- **Tabbed Interface**: Account Info | Personal Info | Address | Contact
- **Wizard Flow**: Multi-step guided update for less experienced users
- **Inline Validation**: Real-time feedback as user types
- **Change Highlighting**: Visual indicators for modified fields
- **Change Summary**: "Review Changes" screen before commit showing before/after
- **Auto-Save Draft**: Periodic saving to prevent data loss
- **Undo/Redo**: Support reverting changes before final commit

### Testing Strategy
- **Unit Tests**: Each validation rule independently
- **Integration Tests**: Database operations, transaction rollback scenarios
- **Concurrency Tests**: Simultaneous updates to same account/customer
- **Validation Tests**: All 30+ validation rules with edge cases
- **Transaction Tests**: Verify rollback if second file update fails
- **Performance Tests**: Update latency with complex validation
- **Security Tests**: Authorization, audit logging, field-level security
- **Data Integrity Tests**: Referential integrity maintained across updates

### Performance Optimization
- Cache lookup tables (state codes, area codes) in memory
- Use compiled queries for frequent operations
- Implement read-through cache for account/customer data
- Consider CQRS: separate read model for display, write model for updates
- Debounce validation during typing
- Lazy load related entities only when needed
- Use AsNoTracking for read-only initial load

### Security Enhancements
- **Field-Level Security**: Some users can view but not edit sensitive fields (SSN, FICO)
- **Audit Trail**: Log ALL changes with user, timestamp, before/after values
- **Data Masking**: Mask SSN in display (*\*\*-\*\*-1234), logs, and audit
- **Authorization**: Role-based access control (who can update accounts/customers)
- **Encryption**: Encrypt PII at rest (SSN, DOB)
- **Rate Limiting**: Prevent automated abuse

### Complexity Metrics
- **Lines of Code**: 4,237 (largest program analyzed)
- **Editable Fields**: 40+ (most complex screen)
- **Validation Routines**: 10+ specialized paragraphs
- **File Operations**: 3 reads, 2 updates (CARDXREF, ACCTDAT, CUSTDAT)
- **State Transitions**: 7+ distinct workflow states
- **Field Comparisons**: 30+ for concurrency check

This program exemplifies enterprise mainframe development at its most sophisticated: comprehensive validation, transactional integrity, optimistic concurrency, and defensive programming throughout.
