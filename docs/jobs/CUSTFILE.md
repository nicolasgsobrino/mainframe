# CUSTFILE

**Source:** [app/jcl/CUSTFILE.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/CUSTFILE.jcl)

Closes the CICS customer file, deletes and redefines the customer data VSAM KSDS cluster, loads it from a flat file, and reopens it in CICS. This fully rebuilds the `AWS.M2.CARDDEMO.CUSTDATA.VSAM.KSDS` dataset.

## Steps

- **CLCIFIL** -- Closes the CUSTDAT file in the CICS region via an SDSF CEMT command.
- **STEP05** -- Deletes the existing customer VSAM KSDS cluster using IDCAMS. Ignores errors (sets MAXCC to 0 if return code is 8 or less).
- **STEP10** -- Defines a new indexed VSAM KSDS cluster for customer data with a 9-byte key at offset 0 and 500-byte fixed-length records.
- **STEP15** -- Copies customer data from the flat file (`AWS.M2.CARDDEMO.CUSTDATA.PS`) into the VSAM cluster using IDCAMS REPRO.
- **OPCIFIL** -- Reopens the CUSTDAT file in the CICS region via an SDSF CEMT command.
