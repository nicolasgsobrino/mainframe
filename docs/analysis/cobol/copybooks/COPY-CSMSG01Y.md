# Copybook Analysis: CSMSG01Y

## Overview
**Source File**: `app/cpy/CSMSG01Y.cpy`
**Type**: Common Message Definitions
**Used By**: All programs (for user feedback messages)

## Purpose
CSMSG01Y defines standard message literals used across the CardDemo application for consistent user feedback. This centralizes message text so changes can be made in one place rather than scattered across all programs.

## Structure Overview
A simple flat structure containing pre-defined message constants, each 50 characters long. Messages are VALUE clauses, making them compile-time constants.

## Key Fields

### User Feedback Messages
- `CCDA-MSG-THANK-YOU` - Exit/completion message ("Thank you for using CardDemo application...")
- `CCDA-MSG-INVALID-KEY` - Error message for invalid function key pressed

## Notable Patterns

### Fixed-Length Messages
All messages are 50 characters with trailing spaces, ensuring consistent display formatting on 3270 screens.

### VALUE Clauses
Uses COBOL VALUE clause for compile-time constants - no runtime memory initialization needed.

### Naming Convention
`CCDA-MSG-{PURPOSE}` pattern makes messages easy to identify and search for in source code.

## Usage Context

**Common across all programs**:
- Included via COPY statement in programs that display user messages
- Referenced directly in screen output operations (e.g., `MOVE CCDA-MSG-THANK-YOU TO SCREEN-MESSAGE`)
- Ensures consistent messaging across the application
- Easy to update for language changes or message refinement

**Limited scope**: This copybook contains only 2 basic messages. Additional messages are likely in CSMSG02Y or embedded in individual programs.
