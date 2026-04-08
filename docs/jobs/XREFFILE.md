# XREFFILE

**Source:** [app/jcl/XREFFILE.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/XREFFILE.jcl)

Deletes and redefines the card cross-reference VSAM KSDS file, loads data from a flat file, then creates an alternate index on the account ID field with a PATH and builds the index.

## Steps

- **STEP05** -- Uses IDCAMS to delete the existing card cross-reference VSAM cluster and its alternate index.
- **STEP10** -- Uses IDCAMS to define a new VSAM KSDS cluster for card cross-references with a 16-byte key and 50-byte fixed-length records.
- **STEP15** -- Uses IDCAMS REPRO to copy data from the flat file (`AWS.M2.CARDDEMO.CARDXREF.PS`) into the newly defined VSAM file.
- **STEP20** -- Uses IDCAMS to define an alternate index (AIX) on the account ID field (key at offset 25, length 11) with non-unique keys, related to the cross-reference base cluster.
- **STEP25** -- Uses IDCAMS to define a PATH (`AWS.M2.CARDDEMO.CARDXREF.VSAM.AIX.PATH`) relating the alternate index to the base cluster.
- **STEP30** -- Uses IDCAMS BLDINDEX to build the alternate index from the base cluster data.
