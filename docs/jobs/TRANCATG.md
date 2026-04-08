# TRANCATG

**Source:** [app/jcl/TRANCATG.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/TRANCATG.jcl)

Deletes, redefines, and loads the transaction category type VSAM KSDS file from a flat file source.

## Steps

- **STEP05** -- Uses IDCAMS to delete the existing transaction category VSAM cluster (`AWS.M2.CARDDEMO.TRANCATG.VSAM.KSDS`), resetting MAXCC to 0.
- **STEP10** -- Uses IDCAMS to define a new VSAM KSDS cluster for transaction categories with a 6-byte key and 60-byte fixed-length records.
- **STEP15** -- Uses IDCAMS REPRO to copy data from the flat file (`AWS.M2.CARDDEMO.TRANCATG.PS`) into the newly defined VSAM file.
