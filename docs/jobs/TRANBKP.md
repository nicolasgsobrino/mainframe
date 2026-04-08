# TRANBKP

**Source:** [app/jcl/TRANBKP.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/TRANBKP.jcl)

Backs up the transaction master VSAM file to a new GDG generation, then deletes and redefines an empty transaction master VSAM cluster. This effectively archives processed transactions and resets the file for new data.

## Steps

- **STEP05R** -- Executes the REPROC procedure to copy (REPRO) the transaction VSAM file (`AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS`) to a new GDG generation of the backup dataset (`AWS.M2.CARDDEMO.TRANSACT.BKUP(+1)`).
- **STEP05** -- Uses IDCAMS to delete the existing transaction master VSAM cluster and its alternate index.
- **STEP10** -- Uses IDCAMS to define a new empty transaction master VSAM KSDS cluster with a 16-byte key and 350-byte fixed-length records.
