# DEFGDGB

**Source:** [app/jcl/DEFGDGB.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/DEFGDGB.jcl)

Defines Generation Data Group (GDG) bases needed by the CardDemo project. Creates six GDG bases with a limit of 5 generations each and the SCRATCH attribute, covering transaction backups, daily transactions, transaction reports, category balance backups, system transactions, and combined transactions.

## Steps

- **STEP05** -- Executes IDCAMS to define six GDG bases: TRANSACT.BKUP, TRANSACT.DALY, TRANREPT, TCATBALF.BKUP, SYSTRAN, and TRANSACT.COMBINED. Each is defined with LIMIT(5) and SCRATCH. Condition code 12 (already exists) is tolerated by resetting MAXCC to 0 after each definition.
