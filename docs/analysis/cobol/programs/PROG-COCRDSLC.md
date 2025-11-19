# Program Analysis: COCRDSLC

## Overview
**Source File**: `app/cbl/COCRDSLC.cbl`
**Type**: Online Transaction - CICS
**Module**: Card Management - Inquiry

## Business Purpose
COCRDSLC provides read-only display of credit card details. It serves as the "view" function in the card management workflow, allowing users to inspect card information without the ability to modify it. This separation between view and edit functionality is a common security and usability pattern.

The program enables users to:
- View complete card details (embossed name, status, expiration)
- Verify card information before update operations
- Look up card details by account number or card number
- Navigate back to the card list after viewing

## Key Logic

### Processing Flow
The program follows CICS pseudo-conversational pattern:

1. **Initial Entry**: Receives control from COCRDLIC with account ID and card number in COMMAREA
2. **Card Retrieval**: Reads CARDDAT file to get card record
3. **Cross-Reference Check**: May read CARDXREF or account files to validate account-to-card relationship
4. **Screen Population**: Maps card data to screen fields (name, status, expiration)
5. **Display**: Sends map to terminal and waits for user response
6. **User Action Processing**:
   - **Enter**: Re-reads card data with potentially new account/card number
   - **F3**: Returns to COCRDLIC (card list)

### Data Retrieval Logic
- **Primary Key Read**: Direct READ on CARDDAT using card number as key
- **Validation**: Verifies account ID matches card-to-account relationship
- **Error Handling**: Displays error message if card not found or access denied
- **Read-Only**: Uses standard READ (not READ UPDATE) since no modifications are made

### Screen Handling
- **Initial Display**: Populates all protected fields from card record
- **Refresh**: Allows user to enter different account/card number and press Enter to view different card
- **Message Display**: Shows informational or error messages in designated screen areas

## Data Dependencies

**Key Copybooks**:
- `CVCRD01Y` - Card master record layout (card number, account ID, CVV, embossed name, expiration date, active status)
- `CVACT02Y` - Account-to-card cross-reference for validation
- `CVCUS01Y` - Customer information (may be used to display additional context)
- `COCOM01Y` - Communication area for passing data between programs
- `COCRDSL` (generated from BMS) - Screen map structure for card detail display

**Files Accessed**:
- `CARDDAT` (Read) - VSAM KSDS indexed by card number, direct read for card details
- `CARDXREF` (Read, optional) - Cross-reference file to validate account-to-card relationships
- `ACCTDAT` (Read, optional) - Account master file for additional context

**Screens**:
- `COCRDSL` - Card detail screen (read-only view)

## Program Relationships

**Called By**: 
- `COCRDLIC` - Card list program (via XCTL when user selects 'S' for view)
- COMMAREA contains selected account ID and card number

**Calls/Transfers To**: 
- `COCRDLIC` - Returns to card list (via XCTL when user presses F3)

**Integration Points**:
- Receives card identification via COMMAREA from calling program
- Preserves navigation context to allow return to card list
- May log inquiry for audit purposes (view access to card data)

## Notable Patterns

### Read-Only Design
This program demonstrates the principle of least privilege - it provides viewing capability without update rights. This pattern is important for:
- **Security**: Limits potential for accidental or unauthorized changes
- **Audit**: Separates view operations from modify operations in logs
- **User Experience**: Simpler interface without validation complexity
- **Role-Based Access**: Some users may have view-only permissions

### Navigation Context Preservation
Program maintains navigation state to support intuitive back-button functionality (F3 returns to list with filters and pagination preserved).

### Flexible Lookup
Supports both entry methods:
- **Direct Navigation**: Arrives with specific card from list selection
- **Manual Lookup**: User can change account/card number and press Enter to view different card

### Error Handling
Displays user-friendly messages for common error scenarios:
- Card not found
- Account-to-card mismatch
- File access errors

## Modernization Considerations

### .NET Migration
- **File I/O**: Replace CICS READ with Entity Framework query
  ```csharp
  var card = await _context.Cards
      .Include(c => c.Account)
      .Include(c => c.Customer)
      .FirstOrDefaultAsync(c => c.CardNumber == cardNumber && c.AccountId == accountId);
  ```
  
- **Screen Handling**: Replace BMS map with MVC view, Razor page, or React component
  
- **Navigation**: Replace XCTL with:
  - MVC: `return RedirectToAction("List", "Card")`
  - API: Return HTTP 200 with card DTO
  - SPA: Update route and component state

### Architecture Impact
- CICS transaction → Web API controller action (GET endpoint)
- Screen map → View model or DTO
- COMMAREA → Route parameters or session state
- Pseudo-conversational → Stateless HTTP request/response

### API Design
```
GET /api/cards/{accountId}/{cardNumber}
```
Returns card details as JSON. Implements:
- Authorization checks (user has permission to view this card)
- Data masking (card number partially masked)
- Related data inclusion (account, customer info as needed)

### Security Enhancements
- **Authentication**: Verify user identity before displaying card data
- **Authorization**: Check user has permission to view cards for this account
- **Data Masking**: Mask sensitive information (show last 4 digits of card number)
- **Audit Logging**: Log who viewed which card and when
- **Rate Limiting**: Prevent automated scraping of card data

### UI/UX Improvements
- Add "Edit" button to transition to update screen (if user has permission)
- Display card information in visually appealing card-shaped element
- Show additional context:
  - Account holder name and contact
  - Current balance and credit limit
  - Recent transaction summary
  - Card type logo (Visa, MasterCard, etc.)
- Breadcrumb navigation
- Related actions: "View Transactions", "View Account", "Report Lost/Stolen"

### Performance Optimization
- Cache card details for frequently viewed cards
- Use async/await for database queries
- Implement read-through cache pattern
- Pre-fetch related data (account, customer) with Include statements
- Consider Redis cache for hot data

### Testing Strategy
- Unit tests for card retrieval logic
- Unit tests for account-to-card validation
- Integration tests for database queries
- Security tests for authorization enforcement
- UI tests for screen display and navigation
- Performance tests for response time under load
