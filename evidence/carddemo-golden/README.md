# CardDemo ADCD Golden Masters

Captured on ADCD `CICSTS61` from the configured Ubuntu host on 2026-05-22.

## CICS

Directory: `cics/`

- `cics_001_cc00_signon`: CardDemo `CC00` sign-on screen.
- `cics_002_admin_menu`: `ADMIN001/PASSWORD` admin menu.
- `cics_003_admin_user_list`: admin user list.
- `cics_010_user_menu`: `USER0001/PASSWORD` user menu.
- `cics_011_account_view_blank`: account view initial screen.
- `cics_012_account_view_00000000001`: populated account view.
- `cics_020_card_list`: credit card list.

Each screen is saved as plain text and x3270 HTML.

## Batch

Directory: `batch/`

Successful final job evidence:

- `golden_CLOSEFIL_JOB00408.spool.txt`: CICS file close request before batch, RC=0000.
- `golden_DALYREJS_JOB00412.spool.txt`: reject-file GDG base definition, RC=0000.
- `golden_TRANBKP_JOB00423.spool.txt`: pre-posting transaction backup/redefine, RC=0000.
- `golden_POSTTRAN_JOB00424.spool.txt`: transaction posting, RC=0004.
- `golden_INTCALC_JOB00427.spool.txt`: interest calculation, RC=0000.
- `golden_TRANBKP_JOB00428.spool.txt`: post-interest transaction backup/redefine, RC=0000.
- `golden_COMBTRAN_JOB00430.spool.txt`: combine transactions, RC=0000.
- `golden_CREASTMT_JOB00434.spool.txt`: statement generation, RC=0000.
- `golden_TRANIDX_JOB00435.spool.txt`: transaction AIX rebuild, RC=0000.
- `golden_TRANREPT_JOB00439.spool.txt`: transaction report, RC=0000.
- `golden_PRTCATBL_JOB00440.spool.txt`: transaction category balance report, RC=0000.
- `golden_OPENFIL_JOB00441.spool.txt`: CICS file reopen, RC=0000.

Exported datasets are in `batch/datasets/`.
