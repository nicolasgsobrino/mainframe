# Program Analysis: COCRDLIC

## Overview
**Source File**: `app/cbl/COCRDLIC.cbl`
**Type**: Online Transaction - CICS
**Module**: Card Management - Inquiry

## Business Purpose
COCRDLIC is the card list inquiry program that allows users to browse credit cards with optional filtering by account number or card number. It provides paginated navigation through card records and supports selection of individual cards for viewing details or making updates. This is the primary entry point for card management operations.

The program serves as a search and navigation hub, enabling:
- Finding cards by account or card number
- Browsing all cards in the system with pagination
- Quick access to card detail viewing (via selection code 'S')
- Quick access to card update functionality (via selection code 'U')

## Key Logic

### Processing Flow
The program follows typical CICS pseudo-conversational pattern:

1. **Initial Entry**: Display empty filter screen with cursor positioned in account number field
2. **Filter Processing**: User enters account/card number filter criteria and presses Enter
3. **Browse Start**: Program queries CARDDAT file based on filter criteria
4. **Page Display**: Shows up to 7 matching cards with pagination controls
5. **Selection Processing**: User enters 'S' or 'U' next to a card and presses Enter
6. **Transfer**: Program validates selection and transfers control to COCRDSLC (view) or COCRDUPC (update)

### Browse Logic
- **STARTBR**: Initiates browse on CARDDAT file with filter key
- **READNEXT**: Reads forward through card records (for F8/forward pagination)
- **READPREV**: Reads backward through card records (for F7/backward pagination)
- **ENDBR**: Terminates browse when user exits or changes filter
- Maintains browse position in COMMAREA between pseudo-conversations
- Displays 7 records per page (typical CICS screen limitation)

### Selection Processing
- Scans selection fields (CRDSEL1 through CRDSEL7) for 'S' or 'U' codes
- Validates only one selection per screen
- Retrieves selected card's account ID and card number
- Sets up COMMAREA with selected card information
- Issues XCTL (transfer control) to target program:
  - 'S' → COCRDSLC (Card Detail View)
  - 'U' → COCRDUPC (Card Update)

### Pagination
- **F8 (Forward)**: Continues browse from current position, displays next 7 records
- **F7 (Backward)**: Repositions browse backward, displays previous 7 records
- Handles end-of-file conditions gracefully (displays message when no more records)
- Preserves filter criteria across page navigation

## Data Dependencies

**Key Copybooks**:
- `CVCRD01Y` - Card master record layout (card number, account ID, status, embossed name, expiration, CVV)
- `CVACT02Y` - Account-to-card cross-reference structure
- `COCOM01Y` - Communication area for passing data between programs (filter criteria, browse position, selected card)
- `COCRDLI` (generated from BMS) - Screen map structure for card list display

**Files Accessed**:
- `CARDDAT` - VSAM KSDS indexed by card number, browsed for card list display
- Alternate index access possible via account number (CVACT02Y structure suggests account-based search)

**Screens**:
- `COCRDLI` - Card list screen with filters, 7-row data display, and pagination controls

## Program Relationships

**Called By**: 
- `COMEN01C` - Main menu (card management option)
- `COCRDSLC` - Card detail view (user presses F3 to return)
- `COCRDUPC` - Card update (user presses F3 to return after update)
- Direct CICS transaction invocation

**Calls/Transfers To**: 
- `COCRDSLC` - Card detail view program (via XCTL when selection = 'S')
- `COCRDUPC` - Card update program (via XCTL when selection = 'U')

**Integration Points**:
- Uses COMMAREA to maintain state across pseudo-conversations
- Preserves filter criteria and browse position
- Passes selected card information to target programs

## Notable Patterns

### Pseudo-Conversational Design
Classic CICS pattern where program terminates after each screen interaction, preserving state in COMMAREA. This approach optimizes CICS resource usage by not holding transactions active during user think time.

### Browse Cursor Management
Maintains browse position using CICS browse commands (STARTBR, READNEXT, READPREV, ENDBR). The program must carefully manage browse state across pseudo-conversations to support pagination.

### Filter Logic
Supports flexible filtering:
- Account number only → Browse account-to-card index
- Card number only → Direct key browse on CARDDAT
- Both specified → Uses card number (more specific)
- Neither specified → Browse all cards (generic key)

### Selection Validation
Enforces single-selection rule by scanning all 7 selection fields and rejecting multiple selections with an error message.

### Screen State Management
Program must reconstruct screen state on each pseudo-conversation:
- Repopulate filter fields from COMMAREA
- Reposition browse cursor
- Refresh displayed card list
- Handle function key pressed (F7, F8, F3, Enter)

## Modernization Considerations

### .NET Migration
- **Browse Pattern**: Replace CICS browse with database query pagination
  - Use OFFSET/FETCH in SQL or Skip/Take in LINQ
  - Example: `SELECT * FROM Cards WHERE ... ORDER BY CardNumber OFFSET @PageSize * @PageNum ROWS FETCH NEXT @PageSize ROWS ONLY`
  
- **Filtering**: Implement dynamic LINQ or SQL WHERE clause building based on filter inputs
  
- **State Management**: Replace COMMAREA with:
  - Session state (for web applications)
  - View state or query parameters (for stateless REST APIs)
  - Application state for temporary browse context
  
- **Selection Processing**: Replace character-based selection with:
  - Button click events (View/Edit buttons per row)
  - Row click events with context menu
  - RESTful links: `/cards/{cardNumber}/view`, `/cards/{cardNumber}/edit`

### Architecture Impact
- CICS transaction → Web controller action or API endpoint
- Screen map → Razor view, React component, or JSON API response
- XCTL transfer → RedirectToAction or SPA route navigation
- COMMAREA → Session storage, view model, or route parameters

### API Design (Modern Approach)
```
GET /api/cards?accountNumber={id}&cardNumber={num}&page={n}&pageSize={size}
```
Response includes:
- Card list (array of card objects)
- Pagination metadata (total count, current page, has next/previous)
- Filter values (for preserving user input)

### UI/UX Improvements
- Increase page size to 20-50 records (modern screens accommodate more)
- Add sortable columns (click header to sort)
- Implement inline actions (icon buttons for view/edit per row)
- Type-ahead search in filter fields
- Highlight matching filter text in results
- Show total record count: "Showing 1-20 of 142 cards"
- Consider infinite scroll or "Load More" as alternative to pagination buttons

### Performance Optimization
- Cache frequently accessed card lists
- Implement database indexes on search fields (account number, card number)
- Use async/await for database queries
- Consider read-through caching for card details
- Lazy loading for large result sets

### Testing Strategy
- Unit tests for filter logic (single filter, combined filters, no filters)
- Unit tests for pagination logic (first page, middle pages, last page, no results)
- Integration tests for database queries with various filter combinations
- UI tests for selection validation (single selection, multiple selection error)
- Performance tests with large datasets (10K+ cards)
