# Copybook Analysis: CSDAT01Y

## Overview
**Source File**: `app/cpy/CSDAT01Y.cpy`
**Type**: Date/Time Data Structures
**Used By**: Programs requiring date/time operations (most programs)

## Purpose
CSDAT01Y defines standardized date and time working storage structures with multiple formatted representations. This provides consistent date/time handling across the application, supporting various display formats and numeric processing.

## Structure Overview
The `WS-DATE-TIME` structure provides overlapping views of date/time data using REDEFINES:
1. **Raw numeric format** (YYYYMMDD, HHMMSSCC)
2. **Separated format** (MM/DD/YY, HH:MM:SS)
3. **ISO timestamp format** (YYYY-MM-DD HH:MM:SS.MMMMMM)

This multi-view approach allows programs to work with dates in the most convenient format for their needs.

## Key Fields

### Core Date/Time (WS-CURDATE-DATA)
- `WS-CURDATE-YEAR/MONTH/DAY` - Individual date components
- `WS-CURDATE-N` - Numeric 8-digit date (REDEFINES WS-CURDATE)
- `WS-CURTIME-HOURS/MINUTE/SECOND/MILSEC` - Time components
- `WS-CURTIME-N` - Numeric 8-digit time (REDEFINES WS-CURTIME)

### Formatted Display Fields
- `WS-CURDATE-MM-DD-YY` - US date format with slashes (MM/DD/YY)
- `WS-CURTIME-HH-MM-SS` - Time with colons (HH:MM:SS)
- `WS-TIMESTAMP` - Full ISO-style timestamp (YYYY-MM-DD HH:MM:SS.MMMMMM)

## Notable Patterns

### REDEFINES for Multiple Views
Uses COBOL REDEFINES to provide both:
- Structured access (individual year/month/day fields)
- Numeric access (single 8-digit number for calculations)

### Pre-Formatted Output
Includes literal separators (/, :, -) in the structure using FILLER fields with VALUE clauses, so programs can:
- Move date components into fields
- Display the entire formatted structure directly

### Millisecond/Microsecond Precision
- `WS-CURTIME-MILSEC` - 2-digit centiseconds (1/100 second)
- `WS-TIMESTAMP-TM-MS6` - 6-digit microseconds (for high precision timestamps)

## Usage Context

**Common pattern in programs**:
1. Call system date/time function (ACCEPT FROM DATE/TIME or CICS ASKTIME)
2. Move result into WS-CURDATE or WS-CURTIME
3. Use appropriate formatted view for display or processing

**Supports**:
- Screen display (formatted with separators)
- Date arithmetic (numeric format)
- Database timestamps (ISO format)
- Audit logging (full timestamp with microseconds)

**Date format note**: Provides both 2-digit year (YY) and 4-digit year (YYYY) formats for Y2K compliance.
