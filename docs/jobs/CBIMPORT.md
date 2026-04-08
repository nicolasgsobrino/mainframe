# CBIMPORT

**Source:** [app/jcl/CBIMPORT.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/CBIMPORT.jcl)

Imports customer data from a multi-record export file and splits it into separate normalized flat files for loading into a target system. Produces customer, account, cross-reference, and transaction output files, plus an error report.

## Steps

- **STEP01** -- Runs the CBIMPORT COBOL program, reading from the consolidated export VSAM file (`AWS.M2.CARDDEMO.EXPORT.DATA`) and writing normalized records to four output sequential files: CUSTOUT (500-byte customer records), ACCTOUT (300-byte account records), XREFOUT (50-byte cross-reference records), and TRNXOUT (350-byte transaction records). Invalid or unrecognized records are written to ERROUT (132-byte error file).
