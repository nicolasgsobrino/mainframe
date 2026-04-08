# READCARD

**Source:** [app/jcl/READCARD.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/READCARD.jcl)

Reads all records from the card master VSAM KSDS file using program CBACT02C and writes output to SYSOUT.

## Steps

- **STEP05** -- Executes program CBACT02C to read the card master VSAM file (`AWS.M2.CARDDEMO.CARDDATA.VSAM.KSDS`) and print its contents.
