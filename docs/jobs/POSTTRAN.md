# POSTTRAN

**Source:** [app/jcl/POSTTRAN.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/POSTTRAN.jcl)

Runs the transaction posting batch program (CBTRN02C) to process the daily transaction file, update the transaction master VSAM file, and maintain transaction category balances.

## Steps

- **STEP15** -- Executes program CBTRN02C. Reads from TRANFILE (transaction master VSAM), DALYTRAN (daily transactions flat file), XREFFILE (card cross-reference VSAM), and ACCTFILE (account data VSAM). Updates TCATBALF (transaction category balance VSAM). Writes rejected transactions to a new generation of the DALYREJS GDG with LRECL=430, RECFM=F.
