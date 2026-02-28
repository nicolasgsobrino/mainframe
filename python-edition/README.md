# CardDemo Python Edition

A faithful Python translation of the AWS CardDemo credit card management system,
originally written in 30,175 lines of COBOL for IBM mainframes.

## What Is This?

CardDemo is an AWS-provided sample application for mainframe modernization scenarios.
The original COBOL implementation uses CICS for online transactions, VSAM for data storage,
BMS for terminal screens, JCL for batch processing, and RACF for security.

This Python edition translates all 18 core business operations into clean, tested Python —
with a modern web interface replacing the 3270 green-screen experience.

## Programs Translated

| COBOL Program | Lines | Python Method | Description |
|---------------|-------|---------------|-------------|
| COSGN00C | 260 | `sign_on()` | User authentication |
| COACTVWC | 941 | `get_account()` | Account view |
| COACTUPC | 4,236 | `update_account()` | Account update |
| COCRDLIC | 1,459 | `list_cards()` | Card list browse |
| COCRDSLC | 887 | `get_card()` | Card view |
| COCRDUPC | 1,560 | `update_card()` | Card update |
| COTRN00C | 699 | `list_transactions()` | Transaction list |
| COTRN01C | 330 | `get_transaction()` | Transaction view |
| COTRN02C | 783 | `add_transaction()` | Transaction add |
| COBIL00C | 572 | `pay_bill()` | Bill payment |
| COUSR00C | 695 | `list_users()` | User list |
| COUSR01C | 299 | `add_user()` | User add |
| COUSR02C | 414 | `update_user()` | User update |
| COUSR03C | 359 | `delete_user()` | User delete |
| CBACT04C | 652 | `calculate_interest()` | Interest calculation (batch) |
| CBTRN02C | 731 | `post_transaction()` | Transaction posting (batch) |
| CBSTM03A | 924 | `generate_statement()` | Statement generation (batch) |
| CBTRN03C | 649 | `generate_report()` | Transaction report (batch) |

**Total: 15,450 → ~400 lines of Python (97% reduction)**

## Bugs Fixed

During the translation process, 14 bugs were identified in the original COBOL source:

1. **COACTUPC** — Phone validation checks NUMA twice instead of NUMC
2. **COACTUPC** — Missing SYNCPOINT ROLLBACK on update failure
3. **COCRDLIC** — Filter type mismatch in card list
4. **COCRDLIC** — Duplicate WHEN clause in EVALUATE
5. **COCRDUPC** — 'EXPIRAION' typo throughout (should be EXPIRATION)
6. **COCRDUPC** — EXIT placement inside conditional block
7. **COTRN00C** — EIBAID precedence error in browse logic
8. **COTRN01C** — Unnecessary READ UPDATE lock for view-only access
9. **COTRN02C** — Validation order issues, no SYNCPOINT
10. **COBIL00C** — No SYNCPOINT rollback if transaction write succeeds but account update fails
11. **COUSR00C** — EIBAID precedence bug in browse
12. **COUSR03C** — Error text says 'Update' instead of 'Delete'
13. **CBACT04C** — Unimplemented 1400-COMPUTE-FEES paragraph
14. **CBTRN02C** — Wrong file status variable (XREFFILE-STATUS vs DALYREJS-STATUS)

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5003 and sign in:
- **Admin:** `ADMIN001` / `PASSWORD`
- **User:** `USER0001` / `PASSWORD`

## Running Tests

```bash
python test_carddemo.py
```

All 49 tests covering the 18 business operations should pass.

## Architecture

```
models.py          — Data models (from COBOL copybooks CVACT01Y, CVCUS01Y, etc.)
services.py        — Business logic (from 18 COBOL programs)
app.py             — Flask web application (replaces CICS/BMS)
index.html         — Web UI (replaces 3270 terminal)
test_carddemo.py   — Comprehensive test suite
```

## License

Same as the original CardDemo — Apache 2.0.
