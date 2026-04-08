# CBADMCDJ

**Source:** [app/jcl/CBADMCDJ.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/CBADMCDJ.jcl)

Creates CICS resource definitions for the CardDemo application by running DFHCSDUP against the CSD file. This defines all mapsets, programs, transactions, and a load library needed by the CardDemo CICS application within the CARDDEMO group.

## Steps

- **STEP1** -- Executes DFHCSDUP in READWRITE mode to batch-update the CICS System Definition (CSD) file. Defines the CARDDEMO group containing: a LIBRARY entry pointing to the application LOADLIB, mapsets for login, account, card, transaction, bill pay, admin, and test screens, programs for each corresponding function (with transaction IDs for login, admin, and test programs), and transaction definitions mapping transaction codes to programs.
