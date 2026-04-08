# COMBTRAN

**Source:** [app/jcl/COMBTRAN.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/COMBTRAN.jcl)

Combines and sorts the current transaction backup file with system-generated transactions, then loads the merged result into the transaction master VSAM file. Uses GDG (Generation Data Group) datasets for versioning.

## Steps

- **STEP05R** -- Sorts the concatenation of the transaction backup GDG (`AWS.M2.CARDDEMO.TRANSACT.BKUP(0)`) and system transactions GDG (`AWS.M2.CARDDEMO.SYSTRAN(0)`) in ascending order by the 16-byte transaction ID, writing the sorted output to a new generation of the combined transactions GDG (`AWS.M2.CARDDEMO.TRANSACT.COMBINED(+1)`).
- **STEP10** -- Loads the newly created combined transaction file into the transaction master VSAM KSDS (`AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS`) using IDCAMS REPRO.
