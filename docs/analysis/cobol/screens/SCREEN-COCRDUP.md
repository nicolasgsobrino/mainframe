# Screen Analysis: COCRDUP

## Overview
**Source File**: `app/bms/COCRDUP.bms`
**Type**: Data Entry and Update
**Program**: COCRDUPC (Card Update)
**Map Name**: CCRDUPA

## Purpose
Provides interface for updating credit card information including embossed name, active status, and expiration date. This screen supports a multi-step update process with validation and confirmation workflow. Users access this screen after selecting a card from the card list (COCRDLI) with the 'U' (update) selection code.

## Screen Layout (24x80)

### Header Section (Lines 1-2)
- Transaction name (TRNNAME)
- Screen title (TITLE01/TITLE02)
- Current date (mm/dd/yy format)
- Current time (hh:mm:ss format)
- Program name (PGMNAME)

### Title (Line 4)
"Update Credit Card Details" - centered, neutral color

### Identification Section (Lines 7-8)
**Key Fields**:
- `ACCTSID` (11 chars, line 7) - Account Number
  - Protected in update mode (cannot change which card being updated)
  - Initial cursor position (IC attribute)
  - Underlined, default color
  
- `CARDSID` (16 chars, line 8) - Card Number
  - Unprot (user enters card number to identify which card to update)
  - Underlined, default color
  - Required field

### Editable Fields Section (Lines 11-15)

- `CRDNAME` (50 chars, line 11) - Name on card
  - Unprot (editable)
  - Embossed name as it appears on physical card
  - Underlined for emphasis
  - Validation: Must be alphabetic characters and spaces
  - Maximum 50 characters

- `CRDSTCD` (1 char, line 13) - Card Active Y/N
  - Unprot (editable)
  - Y = Active card, N = Inactive/cancelled
  - Underlined
  - Validation: Must be 'Y' or 'N'

- `EXPMON` (2 chars, line 15) - Expiry Month
  - Unprot (editable)
  - Format: MM (01-12)
  - Right-justified
  - Validation: Must be 01-12

- `EXPYEAR` (4 chars, line 15) - Expiry Year
  - Unprot (editable)
  - Format: YYYY (full 4-digit year)
  - Right-justified
  - Displayed as MM/YYYY with "/" separator
  - Validation: Must be 1950-2099, cannot be in the past

- `EXPDAY` (2 chars, line 15) - Expiry Day (Hidden)
  - Dark attribute (not visible to user)
  - Protected, set by program
  - Used internally, typically set to last day of expiry month

### Message Areas (Lines 20, 23)
- `INFOMSG` (40 chars, line 20) - Informational messages (e.g., "Press F5 to save changes")
- `ERRMSG` (80 chars, line 23) - Error messages in red, bright (e.g., validation errors)

### Navigation Footer (Line 24)
Function key help (context-sensitive):

**Initial Display** (FKEYS, visible):
- **ENTER** - Process (validate and prepare for save)
- **F3** - Exit (cancel and return to card list)

**Confirmation Mode** (FKEYSC, normally hidden, displayed after Enter):
- **F5** - Save (commit changes to database)
- **F12** - Cancel (discard changes)

The footer changes based on program state, showing Save/Cancel options only after validation.

## Function Keys

### Primary Keys (Always Active)
- **F3**: Exit - Cancel operation and return to COCRDLIC (card list) without saving
- **Enter**: Process - Validate input fields and display confirmation message

### Confirmation Keys (Active After Enter)
- **F5**: Save - Commit changes to CARDDAT file and return to card list
- **F12**: Cancel - Discard changes and return to edit mode or card list

## Workflow Steps

### Step 1: Initial Display
1. Program receives card identification from COCRDLIC via COMMAREA
2. Screen displays with current card values pre-populated
3. Account number protected (identifies the card)
4. Card number may be modifiable or protected depending on entry method
5. Cursor positioned in first editable field (CRDNAME)

### Step 2: User Edits
1. User modifies desired fields (name, status, expiration)
2. Presses Enter to validate changes
3. Program performs field-level validation

### Step 3: Validation
1. Card name must be alphabetic (letters and spaces only)
2. Status must be 'Y' or 'N'
3. Expiration month must be 01-12
4. Expiration year must be valid (1950-2099) and not in past
5. If validation fails: error message displayed, cursor positioned at error field
6. If validation succeeds: confirmation message displayed, F5/F12 options revealed

### Step 4: Confirmation
1. User presses F5 to save or F12 to cancel
2. F5: Program updates CARDDAT file and returns to card list
3. F12: Returns to edit mode or cancels to card list

## Navigation Flow

**Entry Points**:
- From COCRDLIC (card list) via selection code 'U'
- COMMAREA contains account ID and card number

**Exit Points**:
- F3 (any time) → Cancel and return to COCRDLIC
- F12 (after Enter) → Cancel and return to COCRDLIC or edit mode
- F5 (after Enter) → Save changes and return to COCRDLIC with success message

**Related Screens**:
- Previous: COCRDLI (card list)
- Alternative: COCRDSL (card detail view) - accessed via 'S' selection from list

## Technical Characteristics

### Display Attributes
- Color coding: Blue (labels), Yellow (titles), Turquoise (prompts), Red (errors)
- Highlighting: Underline for input fields
- Cursor positioning: Initial cursor (IC) on ACCTSID field
- Protection: Mix of protected (labels, account number) and unprot (editable fields)

### Dynamic Field Control
- FKEYS: Initially visible, contains Enter/F3 instructions
- FKEYSC: Initially dark (hidden), revealed after successful validation, contains F5/F12 instructions
- FKEY05, FKEY12: Separate dark fields that can be made visible independently

### Field Protection
- Account number: Protected (PROT with IC) - identifies card being updated
- Card number: Unprot initially, may become protected after initial read
- Edit fields: Unprot (user can modify)
- Hidden day field: Dark, protected (program-managed)

### Screen Control
- FREEKB: Keyboard unlocked after display
- Storage=AUTO: BMS manages storage
- Mode=INOUT: Supports both input (user edits) and output (data display) operations

## Business Rules

### Validation Rules
1. **Card Name**: Alphabetic characters and spaces only, no numbers or special characters
2. **Active Status**: Must be exactly 'Y' or 'N' (case sensitive)
3. **Expiration Month**: Must be 01-12 (numeric)
4. **Expiration Year**: Must be 1950-2099 (numeric), cannot be in the past
5. **Date Logic**: Program likely validates month/year combination is not expired

### Security and Concurrency
- Program likely implements optimistic locking using REWRITE with file version checking
- Detects concurrent updates and displays error if record changed since initial read

## Modernization Considerations

### Modern UI Equivalent
- Web: Form with input fields, validation, and Save/Cancel buttons
- Desktop: Windows Forms or WPF with data binding and validation
- Mobile: Form screen with native controls and gestures

### UI/UX Improvements
- Replace function key model with button controls:
  - "Save" button (replaces F5)
  - "Cancel" button (replaces F12)
  - "Close" button (replaces F3)
  
- **Field Improvements**:
  - Card name: Show character count (50 characters remaining)
  - Active status: Use toggle switch or dropdown instead of Y/N text entry
  - Expiration: Use date picker or separate month/year dropdowns
  - Add visual card preview showing how embossed name will appear
  
- **Validation Improvements**:
  - Real-time validation as user types (immediate feedback)
  - Inline error messages next to each field
  - Disable Save button until all validations pass
  - Visual indicators (green checkmark, red X) for field validation status
  
- **Confirmation Workflow**:
  - Replace hidden function key reveal with modal dialog: "Save changes to card?"
  - Show change summary before committing
  - Optimistic UI update with background save

### Responsive Design
- Stack fields vertically on mobile
- Large touch-friendly buttons
- Swipe gestures (swipe right to cancel)
- Auto-fill suggestions for card names
- Accessibility: Proper labels, error announcements, keyboard navigation

### API Design (Modern Approach)
```
PUT /api/cards/{accountId}/{cardNumber}
```
Request body:
```json
{
  "embossedName": "John Q. Public",
  "activeStatus": "Y",
  "expirationMonth": 12,
  "expirationYear": 2025
}
```
Response includes updated card with optimistic locking version.

### Validation Implementation
- Client-side: JavaScript/TypeScript for immediate feedback
- Server-side: .NET validation attributes and FluentValidation
- Example:
  ```csharp
  [Required]
  [RegularExpression(@"^[a-zA-Z\s]+$", ErrorMessage = "Card name must contain only letters")]
  [MaxLength(50)]
  public string EmbossedName { get; set; }
  ```

### Concurrency Handling
- Implement ETag-based optimistic concurrency
- Display friendly message if update fails due to concurrent modification
- Offer to reload and retry with latest data
