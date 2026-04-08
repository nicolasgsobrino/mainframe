# READXREF

**Source:** [app/jcl/READXREF.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/READXREF.jcl)

Reads all records from the card cross-reference VSAM KSDS file using program CBACT03C and writes output to SYSOUT.

## Steps

- **STEP05** -- Executes program CBACT03C to read the cross-reference VSAM file (`AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS`) and print its contents.
