# Screen Analysis: COCRDSL

## Overview
**Source File**: `app/bms/COCRDSL.bms`
**Type**: Inquiry/Display (Read-Only)
**Program**: COCRDSLC (Card Detail View)
**Map Name**: CCRDSLA

## Purpose
Displays detailed information for a single credit card in read-only mode. Users access this screen after selecting a card from the card list (COCRDLI) with the 'S' (view) selection code. This provides a focused view of card attributes without the complexity or risk of update functionality.

## Screen Layout (24x80)

### Header Section (Lines 1-2)
- Transaction name (TRNNAME)
- Screen title (TITLE01/TITLE02): "View Credit Card Detail"
- Current date (mm/dd/yy format)
- Current time (hh:mm:ss format)
- Program name (PGMNAME)

### Title (Line 4)
"View Credit Card Detail" - centered, neutral color

### Identification Section (Lines 7-8)
**Input Fields** (key fields to retrieve card):
- `ACCTSID` (11 chars) - Account Number (line 7, col 45)
  - Initial cursor position (IC attribute)
  - Underlined, default color
  - Can be modified to view different card
  
- `CARDSID` (16 chars) - Card Number (line 8, col 45)
  - Underlined, default color
  - Can be modified to view different card

### Card Details Section (Lines 11-15)
**Display Fields** (read-only, protected):

- `CRDNAME` (50 chars, line 11) - Name on card
  - Embossed name as it appears on physical card
  - Underlined for emphasis
  - Maximum 50 characters

- `CRDSTCD` (1 char, line 13) - Card Active Y/N
  - Protected, display-only
  - Y = Active card, N = Inactive/cancelled
  - Underlined

- `EXPMON` (2 chars, line 15) - Expiry Month
  - Protected, display-only
  - Format: MM (01-12)
  - Right-justified

- `EXPYEAR` (4 chars, line 15) - Expiry Year
  - Protected, display-only
  - Format: YYYY (full 4-digit year)
  - Displayed as MM/YYYY with "/" separator

### Message Areas (Lines 20, 23)
- `INFOMSG` (40 chars, line 20) - Informational messages (e.g., "Card found", "Last updated...")
- `ERRMSG` (80 chars, line 23) - Error messages in red, bright (e.g., "Card not found")

### Navigation Footer (Line 24)
Function key help:
- **ENTER** - Search Cards (allows changing account/card number to view different card)
- **F3** - Exit (return to card list)

## Function Keys
- **F3**: Exit - Return to COCRDLIC (card list)
- **Enter**: Search Cards - Refresh display with new account/card number from input fields

## Navigation Flow
**Entry Points**:
- From COCRDLIC (card list) via selection code 'S'
- COMMAREA contains account ID and card number

**Exit Points**:
- F3 → Return to COCRDLIC (card list)
- Enter → Reload card details with new search criteria (remains on COCRDSL screen)

**Related Screens**:
- Previous: COCRDLI (card list)
- Alternative: COCRDUP (card update) - accessed via 'U' selection from list

## Technical Characteristics

### Display Attributes
- Color coding: Blue (labels), Yellow (titles), Turquoise (prompts), Red (errors)
- Highlighting: Underline for data fields
- Cursor positioning: Initial cursor (IC) on ACCTSID field

### Field Protection
- Identification fields (ACCTSID, CARDSID): Unprot (user can modify to view different card)
- Detail fields (CRDNAME, CRDSTCD, EXPMON, EXPYEAR): ASKIP or Prot (read-only display)

### Screen Control
- FREEKB: Keyboard unlocked after display
- Storage=AUTO: BMS manages storage
- Mode=INOUT: Supports both input (account/card ID) and output (card details) operations

## Data Flow
1. User arrives from card list with selected account/card number in COMMAREA
2. Program reads CARDDAT file for the specified card
3. Screen displays card details (name, status, expiration)
4. User can press Enter with new account/card number to view different card
5. User presses F3 to return to card list

## Business Rules
- Display only - no modifications allowed to card data
- Expiration date shown in MM/YYYY format (day not displayed)
- Card status shown as single character Y/N
- CVV code not displayed (security consideration - even in read-only view)

## Modernization Considerations

### Modern UI Equivalent
- Web: Card detail page with read-only form fields or descriptive text
- Desktop: Detail view panel or modal dialog
- Mobile: Full-screen card detail view

### UI/UX Improvements
- Replace function key model with button controls (Back, Edit buttons)
- Add "Edit" button to transition directly to update screen
- Display additional fields:
  - Card type (Visa, MasterCard, Amex)
  - Credit limit
  - Current balance
  - Recent transactions (summary or link)
  - Account holder name and contact info
- Format expiration date more clearly ("Expires: December 2025")
- Add visual card representation (card-shaped UI element with name, number, expiry)
- Show card status more clearly ("Active" vs "Inactive" with color indicator)
- Breadcrumb navigation: Home > Cards > Card List > Card Details
- Add action buttons: "View Transactions", "View Account", "Print Details"

### Responsive Design
- Card-based layout with clear sections
- Stack fields vertically on mobile
- Large touch-friendly buttons for actions
- Swipe gestures for navigation (swipe right to go back)

### Security Considerations
- Mask card number in modern implementation (show last 4 digits: "**** **** **** 1234")
- CVV should never be displayed (not stored in clear text)
- Add audit logging: who viewed which card and when
- Implement role-based access control (not all users should view all cards)

### Accessibility
- Proper labels for screen readers
- High contrast mode support
- Keyboard navigation (Tab, Shift+Tab, Escape for back)
- ARIA attributes for read-only fields
- Focus management when screen loads

### API Design (Modern Approach)
```
GET /api/cards/{accountId}/{cardNumber}
```
Response:
```json
{
  "accountId": "00000000001",
  "cardNumber": "4123456789012345",
  "cardNumberMasked": "**** **** **** 2345",
  "embossedName": "John Q. Public",
  "activeStatus": "Y",
  "expirationMonth": 12,
  "expirationYear": 2025,
  "expirationFormatted": "12/2025",
  "cardType": "Visa"
}
```

### Performance Optimization
- Cache card details for frequently viewed cards
- Pre-fetch related data (account info, recent transactions) for faster navigation
- Use async loading for related data sections
