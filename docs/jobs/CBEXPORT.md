# CBEXPORT

**Source:** [app/jcl/CBEXPORT.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/CBEXPORT.jcl)

Exports customer data from multiple VSAM files into a single consolidated VSAM export file for branch migration or data transfer purposes. Reads from customer, account, cross-reference, transaction, and card data files.

## Steps

- **STEP01** -- Deletes any existing export VSAM cluster, then defines a new indexed VSAM KSDS cluster (`AWS.M2.CARDDEMO.EXPORT.DATA`) with a 4-byte key at offset 28 and 500-byte records.
- **STEP02** -- Runs the CBEXPORT COBOL program, reading from five input VSAM files (CUSTFILE, ACCTFILE, XREFFILE, TRANSACT, CARDFILE) and writing consolidated records to the export VSAM file (EXPFILE).
