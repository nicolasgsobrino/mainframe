# DALYREJS

**Source:** [app/jcl/DALYREJS.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/DALYREJS.jcl)

Defines a Generation Data Group (GDG) base entry for daily transaction rejects. This allows the system to maintain up to 5 generations of reject files with automatic scratch-on-overflow.

## Steps

- **STEP05** -- Defines a GDG base entry named `AWS.M2.CARDDEMO.DALYREJS` using IDCAMS, with a limit of 5 generations and the SCRATCH option to delete the oldest generation when the limit is exceeded.
