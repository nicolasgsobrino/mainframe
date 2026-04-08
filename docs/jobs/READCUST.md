# READCUST

**Source:** [app/jcl/READCUST.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/READCUST.jcl)

Reads all records from the customer master VSAM KSDS file using program CBCUS01C and writes output to SYSOUT.

## Steps

- **STEP05** -- Executes program CBCUS01C to read the customer master VSAM file (`AWS.M2.CARDDEMO.CUSTDATA.VSAM.KSDS`) and print its contents.
