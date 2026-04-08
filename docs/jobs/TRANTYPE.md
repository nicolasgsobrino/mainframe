# TRANTYPE

**Source:** [app/jcl/TRANTYPE.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/TRANTYPE.jcl)

Deletes, redefines, and loads the transaction type VSAM KSDS file from a flat file source.

## Steps

- **STEP05** -- Uses IDCAMS to delete the existing transaction type VSAM cluster (`AWS.M2.CARDDEMO.TRANTYPE.VSAM.KSDS`), resetting MAXCC to 0.
- **STEP10** -- Uses IDCAMS to define a new VSAM KSDS cluster for transaction types with a 2-byte key and 60-byte fixed-length records.
- **STEP15** -- Uses IDCAMS REPRO to copy data from the flat file (`AWS.M2.CARDDEMO.TRANTYPE.PS`) into the newly defined VSAM file.
