# TRANFILE

**Source:** [app/jcl/TRANFILE.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/TRANFILE.jcl)

Closes CICS files, deletes and redefines the transaction master VSAM file, loads initial data from a flat file, creates an alternate index on the processed timestamp field, defines a path for the AIX, builds the index, and reopens the CICS files.

## Steps

- **CLCIFIL** -- Executes SDSF to issue CEMT commands closing the TRANSACT and CXACAIX files in the CICS region.
- **STEP05** -- Uses IDCAMS to delete the existing transaction master VSAM cluster and its alternate index.
- **STEP10** -- Uses IDCAMS to define a new VSAM KSDS cluster for the transaction master with a 16-byte key and 350-byte fixed-length records.
- **STEP15** -- Uses IDCAMS REPRO to copy data from the flat file (`AWS.M2.CARDDEMO.DALYTRAN.PS.INIT`) into the newly defined VSAM file.
- **STEP20** -- Uses IDCAMS to define an alternate index (AIX) on the processed timestamp field (key at offset 304, length 26) related to the transaction master cluster.
- **STEP25** -- Uses IDCAMS to define a PATH relating the alternate index to the base cluster.
- **STEP30** -- Uses IDCAMS BLDINDEX to build the alternate index from the base cluster data.
- **OPCIFIL** -- Executes SDSF to issue CEMT commands reopening the TRANSACT and CXACAIX files in the CICS region.
