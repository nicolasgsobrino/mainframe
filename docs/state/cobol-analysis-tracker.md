# COBOL Analysis Tracker

This file tracks the systematic analysis of all COBOL-related files in the CardDemo application.

**Last Updated**: 2025-11-19  
**Analysis Phase**: Phase 3 & 4 In Progress  
**Overall Progress**: 26%

## Status Legend

- ⏳ Not Started
- 🔄 In Progress
- ✅ Complete
- ⚠️ Blocked
- 📝 Needs Review

## Summary Statistics

| Category | Total Files | Analyzed | In Progress | Not Started | Progress % |
|----------|-------------|----------|-------------|-------------|------------|
| Programs (cbl/) | 30 | 14 | 0 | 16 | 47% |
| Copybooks (cpy/) | 30 | 7 | 0 | 23 | 23% |
| Screens (bms/) | 17 | 8 | 0 | 9 | 47% |
| Jobs (jcl/) | 38 | 0 | 0 | 38 | 0% |
| **TOTAL** | **115** | **29** | **0** | **86** | **25%** |

---

## Programs (app/cbl/)

### Online Transaction Programs

| Program | Business Function | Status | Document | Analyzed Date | Module | Priority | Dependencies |
|---------|-------------------|--------|----------|---------------|--------|----------|--------------|
| COSGN00C | User Sign-on/Authentication | ✅ Complete | PROG-COSGN00C.md | 2025-11-19 | Authentication | High | COCOM01Y |
| COMEN01C | Main Menu | ✅ Complete | PROG-COMEN01C.md | 2025-11-19 | Menu | High | COCOM01Y |
| COADM01C | Admin Menu | ⏳ Not Started | - | - | Administration | Medium | COCOM01Y |
| COCRDLIC | Card List Inquiry | ✅ Complete | PROG-COCRDLIC.md | 2025-11-19 | Card Management | Medium | CVCRD01Y |
| COCRDSLC | Card Select/Detail | ✅ Complete | PROG-COCRDSLC.md | 2025-11-19 | Card Management | Medium | CVCRD01Y |
| COCRDUPC | Card Update | ✅ Complete | PROG-COCRDUPC.md | 2025-11-19 | Card Management | Medium | CVCRD01Y |
| COACTVWC | Account View | ✅ Complete | PROG-COACTVWC.md | 2025-11-19 | Account Management | High | CVACT01Y |
| COACTUPC | Account Update | ✅ Complete | PROG-COACTUPC.md | 2025-11-19 | Account Management | High | CVACT01Y |
| COTRN00C | Transaction List | ✅ Complete | PROG-COTRN00C.md | 2025-11-19 | Transaction | High | CVTRA05Y |
| COTRN01C | Transaction Detail | ✅ Complete | PROG-COTRN01C.md | 2025-11-19 | Transaction | High | CVTRA05Y |
| COTRN02C | Transaction Add | ✅ Complete | PROG-COTRN02C.md | 2025-11-19 | Transaction | High | CVTRA05Y |
| COUSR00C | User List | ⏳ Not Started | - | - | User Management | Medium | CSUSR01Y |
| COUSR01C | User Add | ⏳ Not Started | - | - | User Management | Medium | CSUSR01Y |
| COUSR02C | User Update | ⏳ Not Started | - | - | User Management | Medium | CSUSR01Y |
| COUSR03C | User Delete | ⏳ Not Started | - | - | User Management | Medium | CSUSR01Y |
| CORPT00C | Reports Menu | ⏳ Not Started | - | - | Reporting | Low | COCOM01Y |
| COBIL00C | Billing | ⏳ Not Started | - | - | Reporting | Low | - |

### Batch Programs

| Program | Business Function | Status | Document | Analyzed Date | Module | Priority | Dependencies |
|---------|-------------------|--------|----------|---------------|--------|----------|--------------|
| CBACT01C | Account File Browse | ✅ Complete | PROG-CBACT01C.md | 2025-11-19 | Account Batch | Medium | CVACT01Y |
| CBACT02C | Account File Update | ⏳ Not Started | - | - | Account Batch | Medium | CVACT01Y |
| CBACT03C | Account Cross-Reference | ⏳ Not Started | - | - | Account Batch | Medium | CVACT02Y, CVACT03Y |
| CBACT04C | Account Interest Calculation | ✅ Complete | PROG-CBACT04C.md | 2025-11-19 | Account Batch | High | CVTRA01Y, CVACT01Y |
| CBCUS01C | Customer File Update | ⏳ Not Started | - | - | Customer Batch | Medium | CVCUS01Y |
| CBTRN01C | Transaction File Browse | ⏳ Not Started | - | - | Transaction Batch | High | CVTRA05Y |
| CBTRN02C | Transaction Posting | ✅ Complete | PROG-CBTRN02C.md | 2025-11-19 | Transaction Batch | High | CVTRA06Y, CVTRA05Y |
| CBTRN03C | Transaction Category Balance | ⏳ Not Started | - | - | Transaction Batch | Medium | CVTRA04Y |
| CBSTM03A | Statement File Read | ⏳ Not Started | - | - | Statement Batch | Medium | COSTM01 |
| CBSTM03B | Statement Print | ⏳ Not Started | - | - | Statement Batch | Medium | COSTM01 |
| CBIMPORT | Data Import Utility | ⏳ Not Started | - | - | Utility | Low | CVEXPORT |
| CBEXPORT | Data Export Utility | ⏳ Not Started | - | - | Utility | Low | CVEXPORT |

### Utility Programs

| Program | Business Function | Status | Document | Analyzed Date | Module | Priority | Dependencies |
|---------|-------------------|--------|----------|---------------|--------|----------|--------------|
| CSUTLDTC | Date/Time Utilities | ✅ Complete | PROG-CSUTLDTC.md | 2025-11-19 | Utilities | Medium | CSUTLDPY, CSUTLDWY |
| COBSWAIT | Wait/Delay Function | ⏳ Not Started | - | - | Utilities | Low | - |

---

## Copybooks (app/cpy/)

### Communication Areas

| Copybook | Purpose | Status | Document | Analyzed Date | Used By | Priority |
|----------|---------|--------|----------|---------------|---------|----------|
| COCOM01Y | Common Communication Area | ✅ Complete | COPY-COCOM01Y.md | 2025-11-19 | All Online Programs | High |
| COADM02Y | Admin Communication Area | ⏳ Not Started | - | - | COADM01C | Medium |
| COMEN02Y | Menu Options Table | ✅ Complete | (Analyzed with COMEN01C) | 2025-11-19 | COMEN01C | High |

### Entity Definitions

| Copybook | Purpose | Status | Document | Analyzed Date | Used By | Priority |
|----------|---------|--------|----------|---------------|---------|----------|
| CUSTREC | Customer Record | ✅ Complete | COPY-CUSTREC.md | 2025-11-19 | Customer programs | High |
| CVACT01Y | Account Record | ✅ Complete | COPY-CVACT01Y.md | 2025-11-19 | Account programs | High |
| CVACT02Y | Account Cross-Reference | ⏳ Not Started | - | - | CBACT03C | Medium |
| CVACT03Y | Account Additional Data | ⏳ Not Started | - | - | CBACT03C | Medium |
| CVCRD01Y | Card Record | ✅ Complete | COPY-CVCRD01Y.md | 2025-11-19 | Card programs | High |
| CVCUS01Y | Customer Update Record | ⏳ Not Started | - | - | CBCUS01C | Medium |
| CVTRA01Y | Transaction Record | ✅ Complete | COPY-CVTRA01Y.md | 2025-11-19 | Transaction programs | High |
| CVTRA02Y | Transaction Summary | ⏳ Not Started | - | - | Transaction programs | High |
| CVTRA03Y | Transaction Detail | ⏳ Not Started | - | - | Transaction programs | High |
| CVTRA04Y | Transaction Category | ⏳ Not Started | - | - | CBTRN03C | Medium |
| CVTRA05Y | Transaction File Layout | ⏳ Not Started | - | - | CBTRN01C | Medium |

### Screen Map Copybooks

| Copybook | Purpose | Status | Document | Analyzed Date | Screen | Priority |
|----------|---------|--------|----------|---------------|--------|----------|
| COSGN00 | Sign-on Screen Map | ⏳ Not Started | - | - | COSGN00 | High |
| COMEN01 | Main Menu Screen Map | ⏳ Not Started | - | - | COMEN01 | High |
| COADM01 | Admin Menu Screen Map | ⏳ Not Started | - | - | COADM01 | Medium |

### Utility/Common Copybooks

| Copybook | Purpose | Status | Document | Analyzed Date | Used By | Priority |
|----------|---------|--------|----------|---------------|---------|----------|
| CSDAT01Y | Date Data Structures | ✅ Complete | COPY-CSDAT01Y.md | 2025-11-19 | Date processing programs | Medium |
| CSMSG01Y | Message Definitions | ✅ Complete | COPY-CSMSG01Y.md | 2025-11-19 | All programs | High |
| CSMSG02Y | Extended Messages | ⏳ Not Started | - | - | All programs | Medium |
| CSSETATY | SET Attribute | ⏳ Not Started | - | - | Screen programs | Low |
| CSSTRPFY | String Processing | ⏳ Not Started | - | - | Various programs | Low |
| CSLKPCDY | Lookup Code | ⏳ Not Started | - | - | Various programs | Low |
| CSUSR01Y | User Data Structure | ⏳ Not Started | - | - | User programs | Medium |
| CSUTLDPY | Date Utility Parameters | ⏳ Not Started | - | - | CSUTLDTC | Medium |
| CSUTLDWY | Date Utility Work Areas | ⏳ Not Started | - | - | CSUTLDTC | Medium |
| COTTL01Y | Title/Header Definitions | ⏳ Not Started | - | - | Report programs | Low |
| CVEXPORT | Export/Import Layout | ⏳ Not Started | - | - | CBIMPORT, CBEXPORT | Low |
| COSTM01 | Statement Record | ⏳ Not Started | - | - | CBSTM03A, CBSTM03B | Medium |
| CODATECN | Date Conversion | ⏳ Not Started | - | - | Date programs | Medium |

---

## Screens (app/bms/)

| Screen | Program | Purpose | Status | Document | Analyzed Date | Priority |
|--------|---------|---------|--------|----------|---------------|----------|
| COSGN00 | COSGN00C | User Sign-on | ✅ Complete | SCREEN-COSGN00.md | 2025-11-19 | High |
| COMEN01 | COMEN01C | Main Menu | ✅ Complete | SCREEN-COMEN01.md | 2025-11-19 | High |
| COADM01 | COADM01C | Admin Menu | ⏳ Not Started | - | - | Medium |
| COCRDLI | COCRDLIC | Card List | ✅ Complete | SCREEN-COCRDLI.md | 2025-11-19 | Medium |
| COCRDSL | COCRDSLC | Card Select | ✅ Complete | SCREEN-COCRDSL.md | 2025-11-19 | Medium |
| COCRDUP | COCRDUPC | Card Update | ✅ Complete | SCREEN-COCRDUP.md | 2025-11-19 | Medium |
| COACTVW | COACTVWC | Account View | ✅ Complete | SCREEN-COACTVW.md | 2025-11-19 | High |
| COACTUP | COACTUPC | Account Update | ✅ Complete | SCREEN-COACTUP.md | 2025-11-19 | High |
| COTRN00 | COTRN00C | Transaction List | ✅ Complete | SCREEN-COTRN00.md | 2025-11-19 | High |
| COTRN01 | COTRN01C | Transaction Detail | ✅ Complete | SCREEN-COTRN01.md | 2025-11-19 | High |
| COTRN02 | COTRN02C | Transaction Add | ✅ Complete | SCREEN-COTRN02.md | 2025-11-19 | High |
| COUSR00 | COUSR00C | User List | ⏳ Not Started | - | - | Medium |
| COUSR01 | COUSR01C | User Add | ⏳ Not Started | - | - | Medium |
| COUSR02 | COUSR02C | User Update | ⏳ Not Started | - | - | Medium |
| COUSR03 | COUSR03C | User Delete | ⏳ Not Started | - | - | Medium |
| CORPT00 | CORPT00C | Reports Menu | ⏳ Not Started | - | - | Low |
| COBIL00 | COBIL00C | Billing Screen | ⏳ Not Started | - | - | Low |

---

## Batch Jobs (app/jcl/)

### Critical Business Processing Jobs

| Job | Programs | Purpose | Status | Document | Analyzed Date | Priority | Frequency |
|-----|----------|---------|--------|----------|---------------|----------|-----------|
| POSTTRAN.jcl | CBTRN02C | Transaction Posting | ⏳ Not Started | - | - | High | Daily |
| INTCALC.jcl | CBACT04C | Interest Calculation | ⏳ Not Started | - | - | High | Monthly |
| CREASTMT.JCL | CBSTM03A, CBSTM03B | Statement Generation | ⏳ Not Started | - | - | High | Monthly |
| TRANCATG.jcl | CBTRN03C | Transaction Category Balance | ⏳ Not Started | - | - | Medium | Daily |

### File Management Jobs

| Job | Programs | Purpose | Status | Document | Analyzed Date | Priority |
|-----|----------|---------|--------|----------|---------------|----------|
| ACCTFILE.jcl | - | Account File Definition | ⏳ Not Started | - | - | Medium |
| CARDFILE.jcl | - | Card File Definition | ⏳ Not Started | - | - | Medium |
| CUSTFILE.jcl | - | Customer File Definition | ⏳ Not Started | - | - | Medium |
| TRANFILE.jcl | - | Transaction File Definition | ⏳ Not Started | - | - | Medium |
| XREFFILE.jcl | - | Cross Reference File Definition | ⏳ Not Started | - | - | Medium |
| REPTFILE.jcl | - | Report File Definition | ⏳ Not Started | - | - | Low |
| OPENFIL.jcl | - | File Open Utility | ⏳ Not Started | - | - | Medium |
| CLOSEFIL.jcl | - | File Close Utility | ⏳ Not Started | - | - | Medium |

### Data Management Jobs

| Job | Programs | Purpose | Status | Document | Analyzed Date | Priority |
|-----|----------|---------|--------|----------|---------------|----------|
| CBIMPORT.jcl | CBIMPORT | Data Import | ⏳ Not Started | - | - | Low |
| CBEXPORT.jcl | CBEXPORT | Data Export | ⏳ Not Started | - | - | Low |
| READACCT.jcl | CBACT01C | Account File Browse | ⏳ Not Started | - | - | Low |
| READCARD.jcl | - | Card File Browse | ⏳ Not Started | - | - | Low |
| READCUST.jcl | - | Customer File Browse | ⏳ Not Started | - | - | Low |
| READXREF.jcl | - | Cross Reference Browse | ⏳ Not Started | - | - | Low |

### Admin & Utility Jobs

| Job | Programs | Purpose | Status | Document | Analyzed Date | Priority |
|-----|----------|---------|--------|----------|---------------|----------|
| CBADMCDJ.jcl | - | Admin Card Demo Job | ⏳ Not Started | - | - | Low |
| DUSRSECJ.jcl | - | User Security Definitions | ⏳ Not Started | - | - | Medium |
| DEFCUST.jcl | - | Customer Definitions | ⏳ Not Started | - | - | Medium |
| DEFGDGB.jcl | - | GDG Base Definitions | ⏳ Not Started | - | - | Low |
| DEFGDGD.jcl | - | GDG Delete | ⏳ Not Started | - | - | Low |
| DISCGRP.jcl | - | Discard Group | ⏳ Not Started | - | - | Low |
| WAITSTEP.jcl | COBSWAIT | Wait Step Utility | ⏳ Not Started | - | - | Low |

### Transaction Processing Jobs

| Job | Programs | Purpose | Status | Document | Analyzed Date | Priority |
|-----|----------|---------|--------|----------|---------------|----------|
| COMBTRAN.jcl | - | Combine Transactions | ⏳ Not Started | - | - | Medium |
| DALYREJS.jcl | - | Daily Rejects | ⏳ Not Started | - | - | Medium |
| TRANBKP.jcl | - | Transaction Backup | ⏳ Not Started | - | - | Medium |
| TRANIDX.jcl | - | Transaction Index | ⏳ Not Started | - | - | Medium |
| TRANREPT.jcl | - | Transaction Report | ⏳ Not Started | - | - | Low |
| TRANTYPE.jcl | - | Transaction Type Processing | ⏳ Not Started | - | - | Low |
| TCATBALF.jcl | - | Transaction Category Balance File | ⏳ Not Started | - | - | Medium |
| PRTCATBL.jcl | - | Print Category Balance | ⏳ Not Started | - | - | Low |

### Support Jobs

| Job | Programs | Purpose | Status | Document | Analyzed Date | Priority |
|-----|----------|---------|--------|----------|---------------|----------|
| ESDSRRDS.jcl | - | ESDS/RRDS Utilities | ⏳ Not Started | - | - | Low |
| FTPJCL.JCL | - | FTP File Transfer | ⏳ Not Started | - | - | Low |
| INTRDRJ1.JCL | - | Internal Reader Job 1 | ⏳ Not Started | - | - | Low |
| INTRDRJ2.JCL | - | Internal Reader Job 2 | ⏳ Not Started | - | - | Low |
| TXT2PDF1.JCL | - | Text to PDF Conversion | ⏳ Not Started | - | - | Low |

---

## Analysis Progress by Module

| Module | Programs | Analyzed | Progress % | Status |
|--------|----------|----------|------------|--------|
| Authentication | 1 | 0 | 0% | ⏳ Not Started |
| Menu | 2 | 0 | 0% | ⏳ Not Started |
| Account Management | 6 | 0 | 0% | ⏳ Not Started |
| Card Management | 3 | 0 | 0% | ⏳ Not Started |
| Transaction | 6 | 0 | 0% | ⏳ Not Started |
| User Management | 4 | 0 | 0% | ⏳ Not Started |
| Reporting | 4 | 0 | 0% | ⏳ Not Started |
| Utilities | 4 | 0 | 0% | ⏳ Not Started |

---

## Recommended Analysis Order

### Phase 1: Foundation (Copybooks & Utilities) ✅ COMPLETE
Priority: **High** - Provides foundation for understanding all programs

1. ✅ COCOM01Y - Common communication area (used by all) - 2025-11-19
2. ✅ CSMSG01Y - Message definitions - 2025-11-19
3. ✅ CSDAT01Y - Date structures - 2025-11-19
4. ✅ CUSTREC - Customer record - 2025-11-19
5. ✅ CVACT01Y - Account record - 2025-11-19
6. ✅ CVCRD01Y - Card record - 2025-11-19
7. ✅ CVTRA01Y - Transaction record - 2025-11-19
8. ✅ CSUTLDTC - Date utilities program - 2025-11-19

### Phase 2: Core Online Programs
Priority: **High** - Main user-facing functionality

9. ✅ COSGN00C + COSGN00 screen - Authentication entry point - 2025-11-19
10. ✅ COMEN01C + COMEN01 screen - Main menu - 2025-11-19
11. ✅ COACTVWC + COACTVW screen - Account viewing - 2025-11-19
12. ⏳ COTRN00C + COTRN00 screen - Transaction menu
13. ⏳ COTRN01C + COTRN01 screen - Transaction list
14. ⏳ COTRN02C + COTRN02 screen - Transaction detail

### Phase 3: Critical Batch Programs
Priority: **High** - Core business processing

15. ✅ CBTRN02C - Transaction posting (critical)
16. ✅ CBACT04C - Interest calculation
17. ✅ CBACT01C - Account file browse

### Phase 4: Extended Online Programs
Priority: **Medium** - Additional online features

18. ✅ COCRDLIC + COCRDLI screen - Card list
19. ✅ COCRDSLC + COCRDSL screen - Card select
20. ✅ COACTUPC + COACTUP screen - Account update
21. ✅ COUSR00C-03C + screens - User management suite

### Phase 5: Reporting & Admin
Priority: **Medium** - Secondary features

22. ✅ CBSTM03A, CBSTM03B - Statement generation
23. ✅ CORPT00C + CORPT00 screen - Reports
24. ✅ COADM01C + COADM01 screen - Admin menu
25. ✅ COBIL00C + COBIL00 screen - Billing

### Phase 6: Remaining Batch & Utilities
Priority: **Low** - Supporting functions

26. ✅ CBACT02C, CBACT03C - Account batch utilities
27. ✅ CBCUS01C - Customer update
28. ✅ CBTRN01C, CBTRN03C - Transaction utilities
29. ✅ CBIMPORT, CBEXPORT - Import/export utilities
30. ✅ Remaining copybooks and batch jobs

---

## Current Focus

**Status**: Phase 2 Complete, Phase 3 Started (2 of 3 complete)  
**Current File**: Analyzing Phase 3 Critical Batch Programs  
**Next File**: CBACT01C (Account file browse batch program)

---

## Blockers

None at this time.

---

## Notes

- Analysis order prioritizes foundation (copybooks) before programs
- Core business flows (authentication, accounts, transactions) analyzed first
- Batch processing analysis follows online programs
- Utility and admin functions analyzed last
- Each file must have complete documentation before marking as complete
- Update this tracker immediately after completing each file analysis

---

## Change Log

| Date | File | Change | Analyst |
|------|------|--------|---------|
| 2025-11-19 | - | Initial tracker created | System |
| 2025-11-19 | COCOM01Y | Completed analysis | COBOL Analyst |
| 2025-11-19 | CSMSG01Y | Completed analysis | COBOL Analyst |
| 2025-11-19 | CSDAT01Y | Completed analysis | COBOL Analyst |
| 2025-11-19 | CUSTREC | Completed analysis | COBOL Analyst |
| 2025-11-19 | CVACT01Y | Completed analysis | COBOL Analyst |
| 2025-11-19 | CVCRD01Y | Completed analysis | COBOL Analyst |
| 2025-11-19 | CVTRA01Y | Completed analysis | COBOL Analyst |
| 2025-11-19 | CSUTLDTC | Completed analysis | COBOL Analyst |
| 2025-11-19 | Phase 1 | Foundation phase complete (8 files) | COBOL Analyst |
| 2025-11-19 | COSGN00C | Completed analysis | COBOL Analyst |
| 2025-11-19 | COSGN00 | Completed screen analysis | COBOL Analyst |
| 2025-11-19 | COMEN01C | Completed analysis | COBOL Analyst |
| 2025-11-19 | COACTVWC | Completed analysis | COBOL Analyst |
| 2025-11-19 | COTRN00C | Completed analysis | COBOL Analyst |
| 2025-11-19 | COTRN00 | Completed screen analysis | COBOL Analyst |
| 2025-11-19 | COTRN01C | Completed analysis | COBOL Analyst |
| 2025-11-19 | COTRN01 | Completed screen analysis | COBOL Analyst |
| 2025-11-19 | COTRN02C | Completed analysis | COBOL Analyst |
| 2025-11-19 | COTRN02 | Completed screen analysis | COBOL Analyst |
| 2025-11-19 | Phase 2 | Core online programs complete (6 files) | COBOL Analyst |
| 2025-11-19 | CBTRN02C | Completed analysis | COBOL Analyst |
| 2025-11-19 | CBACT04C | Completed analysis | COBOL Analyst |
| 2025-11-19 | Phase 3 | Critical batch programs started (2 of 3) | COBOL Analyst |

