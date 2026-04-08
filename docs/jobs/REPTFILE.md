# REPTFILE

**Source:** [app/jcl/REPTFILE.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/REPTFILE.jcl)

Defines a Generation Data Group (GDG) for the transaction report output file, allowing up to 10 generations to be retained.

## Steps

- **STEP05** -- Uses IDCAMS to define a GDG base (`AWS.M2.CARDDEMO.TRANREPT`) with a limit of 10 generations.
