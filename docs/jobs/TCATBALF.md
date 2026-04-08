# TCATBALF

**Source:** [app/jcl/TCATBALF.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/TCATBALF.jcl)

Deletes, redefines, and loads the transaction category balance VSAM KSDS file from a flat file source.

## Steps

- **STEP05** -- Uses IDCAMS to delete the existing transaction category balance VSAM cluster (`AWS.M2.CARDDEMO.TCATBALF.VSAM.KSDS`), resetting MAXCC to 0.
- **STEP10** -- Uses IDCAMS to define a new VSAM KSDS cluster for transaction category balances with a 17-byte key and 50-byte fixed-length records.
- **STEP15** -- Uses IDCAMS REPRO to copy data from the flat file (`AWS.M2.CARDDEMO.TCATBALF.PS`) into the newly defined VSAM file.
