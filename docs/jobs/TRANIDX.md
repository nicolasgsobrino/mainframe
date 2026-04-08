# TRANIDX

**Source:** [app/jcl/TRANIDX.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/TRANIDX.jcl)

Defines an alternate index (AIX) on the transaction master VSAM file's processed timestamp field, creates a PATH to relate it to the base cluster, and builds the index.

## Steps

- **STEP20** -- Uses IDCAMS to define an alternate index on the processed timestamp field (key at offset 304, length 26) with non-unique keys, related to the transaction master VSAM cluster.
- **STEP25** -- Uses IDCAMS to define a PATH (`AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX.PATH`) relating the alternate index to the base cluster.
- **STEP30** -- Uses IDCAMS BLDINDEX to build the alternate index from the base cluster data.
