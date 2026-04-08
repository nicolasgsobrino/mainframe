# ACCTFILE

**Source:** [app/jcl/ACCTFILE.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/ACCTFILE.jcl)

Deletes any existing account data VSAM KSDS cluster, defines a new one, and loads it from a flat file. This initializes the `AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS` dataset with account records (300-byte, 11-byte key).

## Steps

- **STEP05** -- Deletes the existing account VSAM KSDS cluster using IDCAMS. Ignores errors (sets MAXCC to 0 if return code is 8 or less).
- **STEP10** -- Defines a new indexed VSAM KSDS cluster for account data with an 11-byte key at offset 0 and 300-byte fixed-length records.
- **STEP15** -- Copies account data from the flat file (`AWS.M2.CARDDEMO.ACCTDATA.PS`) into the newly defined VSAM cluster using IDCAMS REPRO.
