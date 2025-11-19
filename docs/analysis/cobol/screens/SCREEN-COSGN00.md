# Screen Analysis: COSGN00

## Overview
**Source File**: `app/bms/COSGN00.bms`
**Map Name**: COSGN0A (within mapset COSGN00)
**Type**: Data Entry Screen
**Program**: COSGN00C (authentication)

## Purpose
COSGN00 is the sign-on/login screen for the CardDemo application. It's the first screen users see when accessing the system. The screen collects user credentials (User ID and password) and provides a visually appealing interface with ASCII art depicting a dollar bill and application branding.

## Key Fields

### Header Information (Standard across all screens)
- **TRNNAME** - Transaction ID (CC00)
- **PGMNAME** - Program name (COSGN00C)
- **TITLE01/TITLE02** - Application title (40 chars each, centered)
- **CURDATE** - Current date (MM/DD/YY format)
- **CURTIME** - Current time (HH:MM:SS format)
- **APPLID** - CICS application ID
- **SYSID** - CICS system ID

### Input Fields
- **USERID** - User ID entry field (8 characters)
  - Color: Green
  - Attributes: UNPROT (unprotected), IC (initial cursor), FSET
  - Hint: "(8 Char)" displayed after field
  
- **PASSWD** - Password entry field (8 characters)
  - Color: Green
  - Attributes: UNPROT, DRK (dark - hides input), FSET
  - Initial value: "________" (visual indicator)
  - Hint: "(8 Char)" displayed after field

### Output/Display Fields
- **ERRMSG** - Error/status message area (78 characters)
  - Color: Red
  - Position: Line 23 (bottom of screen)
  - Attributes: BRT (bright) for visibility

### Static Content
- Application description: "This is a Credit Card Demo Application for Mainframe Modernization"
- ASCII art: Decorative dollar bill illustration (lines 7-15)
- Instructions: "Type your User ID and Password, then press ENTER:"
- Function key legend: "ENTER=Sign-on  F3=Exit"

## Function Keys

**Active keys**:
- **ENTER** - Submit credentials for authentication
- **F3** - Exit/cancel sign-on (returns thank you message)

## Navigation Flow

### Entry Point
Direct user access via transaction CC00 (application entry point).

### Exit Points
**On successful authentication**:
- Admin users → COADM01C (Admin Menu)
- Regular users → COMEN01C (Main Menu)

**On F3**:
- Displays thank you message and ends session

**On errors**:
- Redisplays COSGN00 with error message

## Screen Layout

**24x80 character screen** (standard 3270):
- Lines 1-3: Header (transaction info, titles, date/time, system IDs)
- Line 5: Application description
- Lines 7-15: ASCII art dollar bill (branding/decoration)
- Line 17: User instructions
- Lines 19-20: Input fields (User ID and Password with hints)
- Line 23: Error message area
- Line 24: Function key legend

## Notable Features

### Color Scheme
- **Blue** - Headers, labels, ASCII art
- **Yellow** - Titles (emphasized)
- **Turquoise** - Input field labels and instructions
- **Green** - Input fields (active/editable areas)
- **Red** - Error messages (bright for visibility)

### User Experience Design
- Cursor auto-positions to User ID field (IC attribute)
- Password field hidden with DRK attribute (security)
- Field length hints displayed "(8 Char)" for clarity
- Decorative ASCII art creates friendly, professional appearance
- Clear instructions before input fields
- Error messages in bright red at bottom of screen

### Technical Attributes
- **FREEKB** - Keyboard unlocked after screen display
- **ALARM** - Terminal alarm on certain conditions
- **ERASE** - Clear screen before display
- **CURSOR** - Position cursor automatically

### Screen Size
24 lines × 80 columns (standard 3270 terminal dimensions)

## Modern UI Equivalent

For web modernization, this screen would become:
- Clean login form with username and password fields
- Responsive design (mobile-friendly)
- Modern branding (replace ASCII art with logo/images)
- "Show/hide password" toggle
- "Forgot password?" link
- Client-side validation
- Loading spinner during authentication
- Success/error toast notifications instead of on-screen message area
- Remember me checkbox (optional)
- Social login buttons (optional)
