# CARDFILE

**Source:** [app/jcl/CARDFILE.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/CARDFILE.jcl)

Closes CICS files, deletes and redefines the card data VSAM KSDS cluster, loads it from a flat file, creates an alternate index on account ID, and reopens the CICS files. This fully rebuilds the `AWS.M2.CARDDEMO.CARDDATA.VSAM.KSDS` dataset with its alternate index path.

## Steps

- **CLCIFIL** -- Closes the CARDDAT and CARDAIX files in the CICS region via SDSF CEMT commands.
- **STEP05** -- Deletes the existing card data VSAM KSDS cluster and its alternate index using IDCAMS.
- **STEP10** -- Defines a new indexed VSAM KSDS cluster for card data with a 16-byte key at offset 0 and 150-byte fixed-length records.
- **STEP15** -- Copies card data from the flat file (`AWS.M2.CARDDEMO.CARDDATA.PS`) into the VSAM cluster using IDCAMS REPRO.
- **STEP40** -- Defines a non-unique alternate index on the account ID field (11-byte key at offset 16) over the card data base cluster.
- **STEP50** -- Defines a PATH to relate the alternate index to the base cluster, enabling access via `AWS.M2.CARDDEMO.CARDDATA.VSAM.AIX.PATH`.
- **STEP60** -- Builds the alternate index cluster from the base KSDS data using IDCAMS BLDINDEX.
- **OPCIFIL** -- Reopens the CARDDAT and CARDAIX files in the CICS region via SDSF CEMT commands.
