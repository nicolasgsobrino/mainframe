# DEFCUST

**Source:** [app/jcl/DEFCUST.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/DEFCUST.jcl)

Deletes and redefines a customer data VSAM KSDS cluster. Unlike CUSTFILE, this job uses a different dataset naming convention (`AWS.CCDA.CUSTDATA` / `AWS.CUSTDATA`) and does not load data or interact with CICS.

## Steps

- **STEP05** (delete) -- Deletes the existing customer VSAM cluster (`AWS.CCDA.CUSTDATA.CLUSTER`) using IDCAMS.
- **STEP05** (define) -- Defines a new indexed VSAM KSDS cluster (`AWS.CUSTDATA.CLUSTER`) with a 10-byte key at offset 0 and 500-byte fixed-length records.
