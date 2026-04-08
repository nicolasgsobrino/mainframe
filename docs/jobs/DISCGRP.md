# DISCGRP

**Source:** [app/jcl/DISCGRP.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/DISCGRP.jcl)

Defines and populates the Disclosure Group VSAM KSDS file. Deletes any existing cluster, defines a new indexed VSAM cluster with a 16-byte key, and loads it from a flat file.

## Steps

- **STEP05** -- Executes IDCAMS to delete the existing DISCGRP.VSAM.KSDS cluster if present. Resets MAXCC to 0 to allow the job to continue if the cluster does not exist.
- **STEP10** -- Executes IDCAMS to define a new VSAM KSDS cluster (DISCGRP.VSAM.KSDS) with 16-byte keys at offset 0, fixed 50-byte records, SHAREOPTIONS(2 3), and the ERASE attribute.
- **STEP15** -- Executes IDCAMS REPRO to copy data from the flat file (DISCGRP.PS) into the newly defined VSAM KSDS cluster.
