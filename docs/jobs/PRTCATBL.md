# PRTCATBL

**Source:** [app/jcl/PRTCATBL.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/PRTCATBL.jcl)

Unloads the transaction category balance VSAM file, backs it up to a GDG generation, then sorts and formats the data into a printable report.

## Steps

- **DELDEF** -- Executes IEFBR14 to delete any existing TCATBALF.REPT report file.
- **STEP05R** -- Executes the REPROC cataloged procedure to unload the TCATBALF VSAM KSDS file into a new generation of the TCATBALF.BKUP GDG with LRECL=50, RECFM=FB.
- **STEP10R** -- Executes SORT to read the newly created GDG generation, sort records by account ID, transaction type code, and transaction category code (all ascending), and format output fields with edited decimal balances. Writes the sorted report to TCATBALF.REPT with LRECL=40, RECFM=FB.
