# CLOSEFIL

**Source:** [app/jcl/CLOSEFIL.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/CLOSEFIL.jcl)

Closes multiple CardDemo VSAM files in the CICS region. This is typically run before batch jobs that need to redefine or reload VSAM datasets that CICS has open.

## Steps

- **CLCIFIL** -- Issues CEMT SET FILE CLOSE commands via SDSF for five CICS file definitions: TRANSACT, CCXREF, ACCTDAT, CXACAIX, and USRSEC.
