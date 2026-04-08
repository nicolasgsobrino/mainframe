# TRANREPT

**Source:** [app/jcl/TRANREPT.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/TRANREPT.jcl)

Unloads the processed transaction VSAM file to a backup GDG, filters and sorts transactions by date range and card number, then produces a formatted transaction report.

## Steps

- **STEP05R (REPROC)** -- Executes the REPROC procedure to copy the transaction VSAM file to a new GDG generation of the backup dataset (`AWS.M2.CARDDEMO.TRANSACT.BKUP(+1)`).
- **STEP05R (SORT)** -- Runs SORT to filter transactions within a parameterized date range and sort them by card number, writing the result to a new daily transaction GDG generation (`AWS.M2.CARDDEMO.TRANSACT.DALY(+1)`).
- **STEP10R** -- Executes program CBTRN03C to produce a formatted transaction report. Reads the sorted daily transactions, card cross-reference, transaction type, transaction category, and date parameter files. Writes the report to a new GDG generation (`AWS.M2.CARDDEMO.TRANREPT(+1)`).
