# READACCT

**Source:** [app/jcl/READACCT.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/READACCT.jcl)

Reads the account master VSAM file and exports the data into multiple flat file formats -- fixed-block compressed, array-based, and variable-block.

## Steps

- **PREDEL** -- Executes IEFBR14 to delete any existing output files: ACCTDATA.PSCOMP, ACCTDATA.ARRYPS, and ACCTDATA.VBPS (disposition MOD,DELETE,DELETE).
- **STEP05** -- Executes program CBACT01C from the CardDemo load library. Reads the account data VSAM KSDS (ACCTDATA.VSAM.KSDS) and writes three output files: OUTFILE (PSCOMP, LRECL=107, RECFM=FB), ARRYFILE (ARRYPS, LRECL=110, RECFM=FB), and VBRCFILE (VBPS, LRECL=84, RECFM=VB).
